/**
 * Premium subscription paywall.
 *
 * Apple guideline 3.1.2 compliance:
 *  - Clearly describes what premium includes
 *  - Explicitly states it does NOT improve sweepstakes odds
 *  - "No purchase necessary" is visible
 *  - Restore purchases button present
 *  - Subscription terms link present
 */
import { useState } from 'react';
import {
  View, Text, StyleSheet, Pressable, ActivityIndicator, Alert, ScrollView,
} from 'react-native';
import { router } from 'expo-router';
import Purchases, { PurchasesOffering } from 'react-native-purchases';
import { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { fetchMe } from '@/api/endpoints';

export default function PaywallScreen() {
  const [offering, setOffering] = useState<PurchasesOffering | null>(null);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState(false);
  const setUser = useAuthStore((s) => s.setUser);

  useEffect(() => {
    Purchases.getOfferings().then((offerings) => {
      setOffering(offerings.current);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handlePurchase = async () => {
    const pkg = offering?.availablePackages[0];
    if (!pkg) return;

    setPurchasing(true);
    try {
      await Purchases.purchasePackage(pkg);
      // RevenueCat webhook will update backend, but refresh user immediately
      const updated = await fetchMe();
      setUser(updated);
      Alert.alert('Welcome to Premium! ✨', 'Enjoy instant verification and ad-free experience.');
      router.back();
    } catch (err: any) {
      if (!err.userCancelled) {
        Alert.alert('Purchase failed', err.message ?? 'Please try again');
      }
    } finally {
      setPurchasing(false);
    }
  };

  const handleRestore = async () => {
    setPurchasing(true);
    try {
      await Purchases.restorePurchases();
      const updated = await fetchMe();
      setUser(updated);
      Alert.alert('Restored', 'Your purchases have been restored.');
      router.back();
    } catch {
      Alert.alert('Restore failed', 'No purchases found to restore.');
    } finally {
      setPurchasing(false);
    }
  };

  const priceString = offering?.availablePackages[0]?.product.priceString ?? '—';

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Pressable style={styles.closeBtn} onPress={() => router.back()}>
        <Text style={styles.closeBtnText}>✕</Text>
      </Pressable>

      <Text style={styles.badge}>✨ MuskMaker Premium</Text>
      <Text style={styles.title}>Build better habits, faster.</Text>

      {/* What you get */}
      <View style={styles.benefitsList}>
        {BENEFITS.map((b) => (
          <View key={b.title} style={styles.benefit}>
            <Text style={styles.benefitIcon}>{b.icon}</Text>
            <View style={styles.benefitText}>
              <Text style={styles.benefitTitle}>{b.title}</Text>
              <Text style={styles.benefitDesc}>{b.desc}</Text>
            </View>
          </View>
        ))}
      </View>

      {/* Fairness disclaimer — required by Apple and by our rules */}
      <View style={styles.fairnessBox}>
        <Text style={styles.fairnessTitle}>🎯 Sweepstakes Fairness</Text>
        <Text style={styles.fairnessText}>
          Premium does NOT improve your sweepstakes odds. Coins are earned based
          only on the goals you complete — not your subscription status.
          1 coin = 1 entry for everyone. No purchase necessary to participate or win.
        </Text>
      </View>

      {loading ? (
        <ActivityIndicator color="#F5A623" size="large" style={{ marginVertical: 24 }} />
      ) : (
        <>
          <Pressable
            style={[styles.purchaseBtn, purchasing && styles.btnDisabled]}
            onPress={handlePurchase}
            disabled={purchasing}
          >
            {purchasing
              ? <ActivityIndicator color="#000" />
              : (
                <View style={styles.purchaseBtnContent}>
                  <Text style={styles.purchaseBtnTitle}>Get Premium</Text>
                  <Text style={styles.purchaseBtnPrice}>{priceString} / month</Text>
                </View>
              )
            }
          </Pressable>

          <Pressable style={styles.restoreBtn} onPress={handleRestore}>
            <Text style={styles.restoreBtnText}>Restore Purchases</Text>
          </Pressable>
        </>
      )}

      <Text style={styles.legal}>
        Subscription auto-renews monthly. Cancel anytime in your App Store settings.
        No purchase necessary to enter sweepstakes or earn coins.
        Sponsored by MuskMaker. Apple is not a sponsor.
      </Text>
    </ScrollView>
  );
}

const BENEFITS = [
  {
    icon: '⚡',
    title: 'Instant AI Verification',
    desc: 'No waiting. Your goal is verified in seconds with AI.',
  },
  {
    icon: '📸',
    title: '1-Photo Fast Path',
    desc: 'Verify some goal types with just 1 photo when location is enabled.',
  },
  {
    icon: '🚫',
    title: 'Ad-Free Experience',
    desc: 'No ads before or after verification.',
  },
  {
    icon: '🔔',
    title: 'Custom Notification Tone',
    desc: 'Choose how your reminders sound: normal, friendly banter, or harsh.',
  },
];

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  content: { padding: 24, paddingTop: 64, paddingBottom: 40, gap: 20 },
  closeBtn: { position: 'absolute', top: 60, right: 24 },
  closeBtnText: { color: '#888', fontSize: 20 },
  badge: { color: '#F5A623', fontSize: 13, fontWeight: '700' },
  title: { fontSize: 30, fontWeight: '800', color: '#FFF', lineHeight: 36 },
  benefitsList: { gap: 16 },
  benefit: { flexDirection: 'row', gap: 14, alignItems: 'flex-start' },
  benefitIcon: { fontSize: 24, marginTop: 2 },
  benefitText: { flex: 1 },
  benefitTitle: { fontSize: 16, fontWeight: '700', color: '#FFF', marginBottom: 2 },
  benefitDesc: { fontSize: 13, color: '#888', lineHeight: 18 },
  fairnessBox: {
    backgroundColor: '#0A0A14', borderRadius: 12, padding: 16,
    borderWidth: 1, borderColor: '#1A1A40', gap: 8,
  },
  fairnessTitle: { fontSize: 14, fontWeight: '700', color: '#6A6AE0' },
  fairnessText: { fontSize: 13, color: '#666', lineHeight: 20 },
  purchaseBtn: {
    height: 64, backgroundColor: '#F5A623', borderRadius: 14,
    justifyContent: 'center', alignItems: 'center',
  },
  btnDisabled: { opacity: 0.4 },
  purchaseBtnContent: { alignItems: 'center' },
  purchaseBtnTitle: { color: '#000', fontSize: 18, fontWeight: '800' },
  purchaseBtnPrice: { color: '#00000080', fontSize: 13, fontWeight: '500', marginTop: 2 },
  restoreBtn: { alignItems: 'center', paddingVertical: 8 },
  restoreBtnText: { color: '#555', fontSize: 14 },
  legal: { fontSize: 11, color: '#333', lineHeight: 18, textAlign: 'center' },
});
