/**
 * AdGate — wraps interstitial ad display for free users.
 *
 * Used in two placements:
 *  1. verification_preroll  — shown before the camera opens
 *  2. verification_postroll — shown after submission
 *
 * Rules:
 *  - Only shown to free (non-premium) users — caller must check isPremium before rendering
 *  - Skippable after 5 seconds (Apple App Review 4.7 compliance)
 *  - onComplete/onSkip are always called even if ad fails to load
 */
import { useEffect, useState, useRef } from 'react';
import { View, Text, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import {
  InterstitialAd,
  AdEventType,
  TestIds,
} from 'react-native-google-mobile-ads';
import Constants from 'expo-constants';

const AD_UNIT_ID = __DEV__
  ? TestIds.INTERSTITIAL
  : (Constants.expoConfig?.extra?.admobInterstitialId ?? TestIds.INTERSTITIAL);

interface AdGateProps {
  placement: 'verification_preroll' | 'verification_postroll';
  onComplete: () => void;
  onSkip: () => void;
}

export function AdGate({ placement, onComplete, onSkip }: AdGateProps) {
  const [adLoaded, setAdLoaded] = useState(false);
  const [adFailed, setAdFailed] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(5);
  const interstitialRef = useRef<InterstitialAd | null>(null);

  useEffect(() => {
    const ad = InterstitialAd.createForAdRequest(AD_UNIT_ID, {
      requestNonPersonalizedAdsOnly: true,
    });

    const loadedSub = ad.addAdEventListener(AdEventType.LOADED, () => {
      setAdLoaded(true);
      ad.show();
    });

    const closedSub = ad.addAdEventListener(AdEventType.CLOSED, () => {
      onComplete();
    });

    const errorSub = ad.addAdEventListener(AdEventType.ERROR, () => {
      setAdFailed(true);
      // If ad fails, proceed without blocking the user
      onComplete();
    });

    interstitialRef.current = ad;
    ad.load();

    return () => {
      loadedSub();
      closedSub();
      errorSub();
    };
  }, []);

  // Countdown timer for manual skip (Apple requires skippable after 5s)
  useEffect(() => {
    if (adFailed) return;
    if (secondsLeft <= 0) return;
    const timer = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [secondsLeft, adFailed]);

  // Loading state while ad request is in flight
  if (!adLoaded && !adFailed) {
    return (
      <View style={styles.container}>
        <ActivityIndicator color="#F5A623" size="large" />
        <Text style={styles.loadingText}>Loading...</Text>
        {/* Allow skip after 5s even during load */}
        {secondsLeft <= 0 && (
          <Pressable style={styles.skipBtn} onPress={onSkip}>
            <Text style={styles.skipBtnText}>Skip</Text>
          </Pressable>
        )}
      </View>
    );
  }

  // Ad is showing via the SDK — this view is behind it
  return (
    <View style={styles.container}>
      {secondsLeft <= 0 && (
        <Pressable style={styles.skipBtn} onPress={onSkip}>
          <Text style={styles.skipBtnText}>Skip Ad</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1, backgroundColor: '#0A0A0A',
    justifyContent: 'center', alignItems: 'center', gap: 16,
  },
  loadingText: { color: '#555', fontSize: 14 },
  skipBtn: {
    position: 'absolute', top: 60, right: 20,
    backgroundColor: 'rgba(0,0,0,0.7)', borderRadius: 20,
    paddingHorizontal: 16, paddingVertical: 8,
    borderWidth: 1, borderColor: '#333',
  },
  skipBtnText: { color: '#FFF', fontSize: 14, fontWeight: '600' },
});
