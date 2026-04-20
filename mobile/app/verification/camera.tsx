/**
 * In-app camera screen — the heart of the anti-cheat system.
 *
 * Rules enforced here:
 *  - No photo library access (camera only)
 *  - Photos taken must be fresh (no file picker)
 *  - Free users: always 2 photos
 *  - Premium standard: always 2 photos
 *  - Premium location path: 1 photo (requires location permission)
 *  - Location is requested ONLY when the user explicitly selects the location path
 *
 * After capture, uploads directly to S3 via pre-signed URL.
 * Shows an interstitial ad BEFORE starting capture (free users only).
 */
import { useRef, useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, Pressable, Alert, ActivityIndicator, Linking,
} from 'react-native';
import { router, useLocalSearchParams, useFocusEffect } from 'expo-router';
import { Camera, useCameraDevice, useCameraPermission } from 'react-native-vision-camera';
import * as Location from 'expo-location';

import { useAuthStore } from '@/stores/authStore';
import { useVerificationStore } from '@/stores/verificationStore';
import { useRequestUploadUrl, useGoal } from '@/api/hooks';
import { uploadPhotoToS3 } from '@/api/endpoints';
import { AdGate } from '@/components/AdGate';
import type { VerificationPath } from '@/types/api';

export default function CameraScreen() {
  const { goalId } = useLocalSearchParams<{ goalId: string }>();
  const user = useAuthStore((s) => s.user);
  const isPremium = user?.subscription_tier === 'premium';
  const { data: goal } = useGoal(goalId);

  const { hasPermission, requestPermission } = useCameraPermission();
  const device = useCameraDevice('back');
  const cameraRef = useRef<Camera>(null);

  const requestUploadUrl = useRequestUploadUrl();
  const {
    startFlow, addPhoto, setPhotoS3Key, setLocation,
    setUploading, photos, verificationPath, requiredPhotoCount,
    goalId: flowGoalId,
  } = useVerificationStore();

  const [isCameraActive, setIsCameraActive] = useState(true);
  useFocusEffect(
    useCallback(() => {
      setIsCameraActive(true);
      return () => setIsCameraActive(false);
    }, [])
  );

  const [adDismissed, setAdDismissed] = useState(isPremium); // premium users skip ad
  const [capturing, setCapturing] = useState(false);
  const [selectedPath, setSelectedPath] = useState<VerificationPath | null>(
    flowGoalId === goalId ? verificationPath : null,
  );
  // Only show path selector on the first mount for this goal.
  // If the flow is already in progress (flowGoalId === goalId), the path was
  // chosen earlier — skip straight to camera.
  const [showPathSelector, setShowPathSelector] = useState(
    isPremium && flowGoalId !== goalId,
  );

  const required = requiredPhotoCount();
  const capturedCount = photos.length;

  // ── Path selection (premium only) ─────────────────────────────────────────
  useEffect(() => {
    if (!isPremium && goal) {
      // Free users have no choice — always free_manual
      setSelectedPath('free_manual');
      setShowPathSelector(false);
      // Only initialize the flow if it hasn't been started for this goal yet.
      // startFlow resets the store (including photos), so calling it on every
      // camera remount (e.g. when returning from the preview screen for photo 2)
      // would wipe the already-captured photo 1.
      if (flowGoalId !== goalId) {
        startFlow(goalId, 'free_manual');
      }
    }
  }, [isPremium, goal, goalId, flowGoalId]);

  const handleSelectPath = async (path: VerificationPath) => {
    if (path === 'premium_ai_location') {
      // Request location permission only for this path
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert(
          'Location required',
          'The 1-photo fast path requires location access. Allow it in Settings or use the standard 2-photo path instead.',
          [
            { text: 'Open Settings', onPress: () => Linking.openSettings() },
            { text: 'Use 2 photos', onPress: () => handleSelectPath('premium_ai_standard') },
            { text: 'Cancel' },
          ]
        );
        return;
      }
      // Capture location now
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      startFlow(goalId, path);
      setLocation({
        lat: loc.coords.latitude,
        lng: loc.coords.longitude,
        accuracyMeters: loc.coords.accuracy ?? 100,
        capturedAt: new Date().toISOString(),
      });
    } else {
      startFlow(goalId, path);
    }
    setSelectedPath(path);
    setShowPathSelector(false);
  };

  // ── Camera permission ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!hasPermission) requestPermission();
  }, [hasPermission]);

  const capturePhoto = useCallback(async () => {
    if (!cameraRef.current || capturing) return;
    setCapturing(true);
    try {
      const photo = await cameraRef.current.takePhoto({ flash: 'off' });
      const photoIndex = capturedCount; // 0-based

      // Get pre-signed upload URL
      const { upload_url, s3_key } = await requestUploadUrl.mutateAsync({
        goal_id: goalId,
        photo_index: photoIndex,
        mime_type: 'image/jpeg',
      });

      // Add photo to store immediately (for preview)
      addPhoto({ uri: `file://${photo.path}`, s3Key: null, photoIndex });

      // Upload to S3
      setUploading(true);
      await uploadPhotoToS3(upload_url, `file://${photo.path}`);
      setPhotoS3Key(photoIndex, s3_key);
      setUploading(false);

      // Replace camera with preview so camera is removed from the stack
      router.replace(`/verification/preview?goalId=${goalId}&photoIndex=${photoIndex}`);
    } catch (err: any) {
      Alert.alert('Capture failed', err.detail ?? err.message ?? 'Please try again');
    } finally {
      setCapturing(false);
    }
  }, [capturing, capturedCount, goalId]);

  // ── Pre-roll ad (free users) ───────────────────────────────────────────────
  if (!adDismissed) {
    return (
      <AdGate
        placement="verification_preroll"
        onComplete={() => setAdDismissed(true)}
        onSkip={() => setAdDismissed(true)}
      />
    );
  }

  // ── Premium path selector ──────────────────────────────────────────────────
  if (showPathSelector && isPremium && goal) {
    const supportsLocation = goal.goal_type.supports_location_path;
    return (
      <View style={styles.pathSelector}>
        <Text style={styles.pathTitle}>Choose verification method</Text>
        <Text style={styles.pathSubtitle}>{goal.goal_type.name}</Text>

        <Pressable
          style={styles.pathOption}
          onPress={() => handleSelectPath('premium_ai_standard')}
        >
          <Text style={styles.pathOptionTitle}>📸 Standard (2 photos)</Text>
          <Text style={styles.pathOptionDesc}>Instant AI review · no location required</Text>
        </Pressable>

        {supportsLocation && (
          <Pressable
            style={[styles.pathOption, styles.pathOptionHighlight]}
            onPress={() => handleSelectPath('premium_ai_location')}
          >
            <Text style={styles.pathOptionTitle}>⚡ Fast (1 photo + location)</Text>
            <Text style={styles.pathOptionDesc}>
              Fastest path · requires location access · instant AI review
            </Text>
          </Pressable>
        )}

        <Pressable style={styles.cancelBtn} onPress={() => router.back()}>
          <Text style={styles.cancelBtnText}>Cancel</Text>
        </Pressable>
      </View>
    );
  }

  if (!hasPermission) {
    return (
      <View style={styles.permissionContainer}>
        <Text style={styles.permissionText}>Camera access is required to verify goals.</Text>
        <Pressable style={styles.permissionBtn} onPress={requestPermission}>
          <Text style={styles.permissionBtnText}>Grant Permission</Text>
        </Pressable>
      </View>
    );
  }

  if (!device) {
    return <View style={styles.container}><ActivityIndicator color="#F5A623" /></View>;
  }

  const isLastPhoto = capturedCount === required - 1;

  return (
    <View style={styles.container}>
      <Camera
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        device={device}
        isActive={isCameraActive}
        photo={true}
      />

      {/* Photo counter */}
      <View style={styles.counterBadge}>
        <Text style={styles.counterText}>
          Photo {capturedCount + 1} of {required}
        </Text>
      </View>

      {/* Instruction overlay */}
      <View style={styles.instructionOverlay}>
        {selectedPath === 'free_manual' && (
          <Text style={styles.instructionText}>
            {capturedCount === 0
              ? 'Photo 1: Show yourself doing the activity'
              : 'Photo 2: Show the context / environment'}
          </Text>
        )}
        {selectedPath === 'premium_ai_standard' && (
          <Text style={styles.instructionText}>
            {capturedCount === 0
              ? 'Photo 1: Clear view of the activity'
              : 'Photo 2: Wider context shot'}
          </Text>
        )}
        {selectedPath === 'premium_ai_location' && (
          <Text style={styles.instructionText}>
            Take 1 clear photo showing your activity
          </Text>
        )}
      </View>

      {/* Capture button */}
      <View style={styles.controls}>
        <Pressable
          style={[styles.captureButton, capturing && styles.captureButtonDisabled]}
          onPress={capturePhoto}
          disabled={capturing}
        >
          {capturing
            ? <ActivityIndicator color="#000" size="large" />
            : <View style={styles.captureButtonInner} />
          }
        </Pressable>
      </View>

      {/* Cancel */}
      <Pressable style={styles.cancelOverlay} onPress={() => router.back()}>
        <Text style={styles.cancelOverlayText}>✕</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  counterBadge: {
    position: 'absolute', top: 60, alignSelf: 'center',
    backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 20,
    paddingHorizontal: 16, paddingVertical: 6,
  },
  counterText: { color: '#FFF', fontSize: 14, fontWeight: '600' },
  instructionOverlay: {
    position: 'absolute', bottom: 160, left: 20, right: 20,
    backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 12, padding: 12,
  },
  instructionText: { color: '#FFF', fontSize: 14, textAlign: 'center' },
  controls: {
    position: 'absolute', bottom: 60, left: 0, right: 0,
    alignItems: 'center',
  },
  captureButton: {
    width: 80, height: 80, borderRadius: 40,
    backgroundColor: '#FFF', justifyContent: 'center', alignItems: 'center',
    borderWidth: 4, borderColor: '#F5A623',
  },
  captureButtonDisabled: { opacity: 0.5 },
  captureButtonInner: { width: 60, height: 60, borderRadius: 30, backgroundColor: '#FFF' },
  cancelOverlay: { position: 'absolute', top: 60, left: 20 },
  cancelOverlayText: { color: '#FFF', fontSize: 24 },
  // Path selector
  pathSelector: {
    flex: 1, backgroundColor: '#0A0A0A', padding: 24, paddingTop: 80, gap: 16,
  },
  pathTitle: { fontSize: 24, fontWeight: '800', color: '#FFF' },
  pathSubtitle: { fontSize: 16, color: '#888', marginBottom: 8 },
  pathOption: {
    backgroundColor: '#1A1A1A', borderRadius: 14, padding: 20,
    borderWidth: 1, borderColor: '#333',
  },
  pathOptionHighlight: { borderColor: '#F5A623' },
  pathOptionTitle: { fontSize: 17, fontWeight: '700', color: '#FFF', marginBottom: 4 },
  pathOptionDesc: { fontSize: 13, color: '#888', lineHeight: 18 },
  cancelBtn: { marginTop: 8, alignItems: 'center' },
  cancelBtnText: { color: '#555', fontSize: 15 },
  // Permission
  permissionContainer: {
    flex: 1, backgroundColor: '#0A0A0A', justifyContent: 'center', alignItems: 'center', gap: 20,
  },
  permissionText: { color: '#888', fontSize: 16, textAlign: 'center', paddingHorizontal: 32 },
  permissionBtn: {
    backgroundColor: '#F5A623', borderRadius: 12, paddingHorizontal: 24, paddingVertical: 14,
  },
  permissionBtnText: { color: '#000', fontWeight: '700', fontSize: 15 },
});
