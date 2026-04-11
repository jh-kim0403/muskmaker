/**
 * Verification status screen.
 *
 * - Premium AI pass: shows coins awarded immediately
 * - Free tier / AI uncertain: shows "under review" with polling
 * - Rejected: shows reason
 */
import { View, Text, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useVerificationStatus } from '@/api/hooks';
import { useAuthStore } from '@/stores/authStore';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

export default function VerificationStatusScreen() {
  const { verificationId } = useLocalSearchParams<{ verificationId: string }>();
  const isPremium = useAuthStore((s) => s.isPremium)();
  const setUser = useAuthStore((s) => s.setUser);
  const qc = useQueryClient();

  const { data: verification, isLoading } = useVerificationStatus(
    verificationId,
    !!verificationId
  );

  // When verification is approved, refresh user (coin balance update)
  useEffect(() => {
    if (verification?.status === 'approved' && verification.coins_awarded > 0) {
      qc.invalidateQueries({ queryKey: ['me'] });
    }
  }, [verification?.status]);

  if (isLoading || !verification) {
    return (
      <View style={styles.container}>
        <ActivityIndicator color="#F5A623" size="large" />
      </View>
    );
  }

  const { status, coins_awarded, rejection_reason, verification_path } = verification;

  const isManualReview = status === 'pending_review' || status === 'in_review';

  return (
    <View style={styles.container}>
      {/* Approved */}
      {status === 'approved' && (
        <View style={styles.resultBox}>
          <Text style={styles.resultEmoji}>🎉</Text>
          <Text style={styles.resultTitle}>Verified!</Text>
          <Text style={styles.resultSubtitle}>
            +{coins_awarded} coin{coins_awarded !== 1 ? 's' : ''} added to your balance
          </Text>
          {isPremium && (
            <Text style={styles.resultNote}>Instant AI verification ✨</Text>
          )}
        </View>
      )}

      {/* Pending manual review (free tier) */}
      {isManualReview && (
        <View style={styles.resultBox}>
          <Text style={styles.resultEmoji}>⏳</Text>
          <Text style={styles.resultTitle}>Under Review</Text>
          <Text style={styles.resultSubtitle}>
            Your verification is in the review queue.{'\n'}
            This typically takes up to 24 hours.
          </Text>
          <Text style={styles.resultNote}>
            We'll notify you when it's approved.
          </Text>
          <View style={styles.premiumHint}>
            <Text style={styles.premiumHintText}>
              ✨ Premium members get instant AI verification with no wait time.
            </Text>
            <Pressable onPress={() => router.push('/paywall')}>
              <Text style={styles.premiumHintCta}>Upgrade →</Text>
            </Pressable>
          </View>
        </View>
      )}

      {/* Rejected */}
      {status === 'rejected' && (
        <View style={styles.resultBox}>
          <Text style={styles.resultEmoji}>❌</Text>
          <Text style={styles.resultTitle}>Not Approved</Text>
          {rejection_reason && (
            <Text style={styles.rejectionReason}>{rejection_reason}</Text>
          )}
          <Text style={styles.resultNote}>
            You can try again tomorrow with a new goal of this type.
          </Text>
        </View>
      )}

      <Pressable style={styles.homeBtn} onPress={() => router.replace('/(tabs)')}>
        <Text style={styles.homeBtnText}>Back to Home</Text>
      </Pressable>

      {status === 'approved' && (
        <Pressable
          style={styles.enterSweepBtn}
          onPress={() => router.push('/(tabs)/sweepstakes')}
        >
          <Text style={styles.enterSweepBtnText}>Use Coins in Sweepstakes →</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1, backgroundColor: '#0A0A0A', padding: 24, paddingTop: 80,
    justifyContent: 'center', gap: 16,
  },
  resultBox: { alignItems: 'center', gap: 12 },
  resultEmoji: { fontSize: 64 },
  resultTitle: { fontSize: 30, fontWeight: '800', color: '#FFF', textAlign: 'center' },
  resultSubtitle: { fontSize: 16, color: '#888', textAlign: 'center', lineHeight: 24 },
  resultNote: { fontSize: 13, color: '#555', textAlign: 'center' },
  rejectionReason: {
    fontSize: 15, color: '#E05A4E', textAlign: 'center',
    backgroundColor: '#1A0A0A', borderRadius: 10, padding: 12, lineHeight: 22,
  },
  premiumHint: {
    backgroundColor: '#1A1200', borderRadius: 10, padding: 16,
    borderWidth: 1, borderColor: '#F5A62340', alignItems: 'center', gap: 8, marginTop: 8,
  },
  premiumHintText: { color: '#888', fontSize: 13, textAlign: 'center' },
  premiumHintCta: { color: '#F5A623', fontWeight: '700', fontSize: 14 },
  homeBtn: {
    height: 56, backgroundColor: '#1A1A1A', borderRadius: 12,
    justifyContent: 'center', alignItems: 'center', marginTop: 24,
  },
  homeBtnText: { color: '#FFF', fontSize: 16, fontWeight: '600' },
  enterSweepBtn: {
    height: 56, backgroundColor: '#F5A623', borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
  },
  enterSweepBtnText: { color: '#000', fontSize: 16, fontWeight: '700' },
});
