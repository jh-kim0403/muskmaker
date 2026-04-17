/**
 * Photo preview screen — shown after each capture.
 * User can retake or confirm. After all photos are confirmed, submits verification.
 */
import { View, Text, Image, StyleSheet, Pressable, ActivityIndicator, Alert } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useVerificationStore } from '@/stores/verificationStore';
import { useSubmitVerification } from '@/api/hooks';
import { useAuthStore } from '@/stores/authStore';
import { AdGate } from '@/components/AdGate';
import { useState } from 'react';

export default function PreviewScreen() {
  const { goalId, photoIndex: indexParam } = useLocalSearchParams<{
    goalId: string;
    photoIndex: string;
  }>();
  const photoIndex = parseInt(indexParam ?? '0', 10);

  const {
    photos, verificationPath, location, requiredPhotoCount, isReadyToSubmit, resetFlow, removePhoto,
  } = useVerificationStore();
  const submitVerification = useSubmitVerification();
  const setUser = useAuthStore((s) => s.setUser);
  const user = useAuthStore((s) => s.user);
  const isPremium = user?.subscription_tier === 'premium';

  const [showPostAd, setShowPostAd] = useState(false);
  const [submittedVerification, setSubmittedVerification] = useState<any>(null);

  const currentPhoto = photos.find((p) => p.photoIndex === photoIndex);
  const required = requiredPhotoCount();
  const needsMorePhotos = photos.length < required;

  const handleRetake = () => {
    removePhoto(photoIndex);
    router.back();
  };

  const handleConfirmAndNext = () => {
    if (needsMorePhotos) {
      // Go back to camera for next photo
      router.replace(`/verification/camera?goalId=${goalId}`);
    } else {
      // All photos captured — submit
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    if (!isReadyToSubmit()) {
      Alert.alert('Not ready', 'Please ensure all photos are uploaded before submitting.');
      return;
    }

    const s3Keys = photos
      .sort((a, b) => a.photoIndex - b.photoIndex)
      .map((p) => p.s3Key!);

    try {
      const verification = await submitVerification.mutateAsync({
        goal_id: goalId,
        verification_path: verificationPath!,
        photo_s3_keys: s3Keys,
        location_lat: location?.lat,
        location_lng: location?.lng,
        location_accuracy_meters: location?.accuracyMeters,
        location_captured_at: location?.capturedAt,
      });

      setSubmittedVerification(verification);

      // Show post-submission ad for free users
      if (!isPremium) {
        setShowPostAd(true);
      } else {
        navigateToStatus(verification);
      }
    } catch (err: any) {
      Alert.alert('Submission failed', err.detail ?? 'Please try again');
    }
  };

  const navigateToStatus = (verification: any) => {
    resetFlow();
    router.replace(`/verification/status?verificationId=${verification.id}`);
  };

  // Post-submission ad (free users only)
  if (showPostAd && submittedVerification) {
    return (
      <AdGate
        placement="verification_postroll"
        onComplete={() => navigateToStatus(submittedVerification)}
        onSkip={() => navigateToStatus(submittedVerification)}
      />
    );
  }

  if (!currentPhoto) {
    return <View style={styles.container} />;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.header}>
        Photo {photoIndex + 1} of {required}
      </Text>

      <Image source={{ uri: currentPhoto.uri }} style={styles.preview} resizeMode="cover" />

      {/* Upload status */}
      {currentPhoto.s3Key === null && (
        <View style={styles.uploadBadge}>
          <ActivityIndicator size="small" color="#F5A623" />
          <Text style={styles.uploadText}>Uploading...</Text>
        </View>
      )}

      {currentPhoto.s3Key !== null && (
        <View style={styles.uploadBadge}>
          <Text style={styles.uploadDone}>✓ Uploaded</Text>
        </View>
      )}

      <View style={styles.actions}>
        <Pressable style={styles.retakeBtn} onPress={handleRetake}>
          <Text style={styles.retakeBtnText}>Retake</Text>
        </Pressable>

        <Pressable
          style={[
            styles.nextBtn,
            (currentPhoto.s3Key === null || submitVerification.isPending) && styles.btnDisabled,
          ]}
          onPress={handleConfirmAndNext}
          disabled={currentPhoto.s3Key === null || submitVerification.isPending}
        >
          {submitVerification.isPending ? (
            <ActivityIndicator color="#000" />
          ) : (
            <Text style={styles.nextBtnText}>
              {needsMorePhotos ? `Next Photo →` : 'Submit Verification'}
            </Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A', padding: 20, paddingTop: 60 },
  header: { fontSize: 18, fontWeight: '700', color: '#FFF', marginBottom: 16, textAlign: 'center' },
  preview: { flex: 1, borderRadius: 16, marginBottom: 16 },
  uploadBadge: {
    flexDirection: 'row', justifyContent: 'center', alignItems: 'center',
    gap: 8, marginBottom: 16,
  },
  uploadText: { color: '#F5A623', fontSize: 14 },
  uploadDone: { color: '#6AB06A', fontSize: 14, fontWeight: '600' },
  actions: { flexDirection: 'row', gap: 12 },
  retakeBtn: {
    flex: 1, height: 56, backgroundColor: '#1A1A1A', borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
  },
  retakeBtnText: { color: '#FFF', fontSize: 15, fontWeight: '600' },
  nextBtn: {
    flex: 2, height: 56, backgroundColor: '#F5A623', borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
  },
  btnDisabled: { opacity: 0.4 },
  nextBtnText: { color: '#000', fontSize: 15, fontWeight: '700' },
});
