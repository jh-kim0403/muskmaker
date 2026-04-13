/**
 * Profile tab — settings, subscription, notification preferences.
 */
import { View, Text, StyleSheet, Pressable, Switch, Alert, ScrollView } from 'react-native';
import { router } from 'expo-router';
import { getAuth, signOut } from '@react-native-firebase/auth';

const firebaseAuth = getAuth();

import { useMe, useNotificationPreferences, useUpdateNotificationPreferences } from '@/api/hooks';
import { useAuthStore } from '@/stores/authStore';

export default function ProfileTab() {
  const { data: user } = useMe();
  const { data: prefs } = useNotificationPreferences();
  const updatePrefs = useUpdateNotificationPreferences();
  const { clearAuth, isPremium: isPremiumFn } = useAuthStore();
  const isPremium = isPremiumFn();

  const handleSignOut = async () => {
    Alert.alert('Sign out', 'Are you sure?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign out', style: 'destructive',
        onPress: async () => {
          await signOut(firebaseAuth);
          clearAuth();
        },
      },
    ]);
  };

  const togglePref = (key: string, value: boolean) => {
    updatePrefs.mutate({ [key]: value });
  };

  const setTone = (tone: 'normal' | 'friendly_banter' | 'harsh') => {
    if (!isPremium) {
      Alert.alert('Premium required', 'Custom notification tones are a premium feature.');
      return;
    }
    updatePrefs.mutate({ notification_tone: tone });
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* User info */}
      <View style={styles.userCard}>
        <Text style={styles.userName}>{user?.display_name ?? 'Anonymous'}</Text>
        <Text style={styles.userEmail}>{user?.email ?? ''}</Text>
        <View style={[styles.tierBadge, isPremium && styles.tierBadgePremium]}>
          <Text style={styles.tierBadgeText}>{isPremium ? '✨ Premium' : 'Free'}</Text>
        </View>
        <Text style={styles.timezone}>🌍 {user?.timezone ?? 'UTC'}</Text>
      </View>

      {/* Subscription */}
      {!isPremium && (
        <Pressable style={styles.upgradeBtn} onPress={() => router.push('/paywall')}>
          <Text style={styles.upgradeBtnText}>✨ Upgrade to Premium</Text>
          <Text style={styles.upgradeBtnSub}>Instant AI verification · No ads · Custom tones</Text>
        </Pressable>
      )}

      {/* Notification settings */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Notifications</Text>

        <ToggleRow
          label="Push notifications"
          value={prefs?.push_enabled ?? true}
          onToggle={(v) => togglePref('push_enabled', v)}
        />
        <ToggleRow
          label="Goal expiry reminders"
          value={prefs?.goal_reminder_enabled ?? true}
          onToggle={(v) => togglePref('goal_reminder_enabled', v)}
        />
        <ToggleRow
          label="Sweepstakes results"
          value={prefs?.sweep_result_enabled ?? true}
          onToggle={(v) => togglePref('sweep_result_enabled', v)}
        />
      </View>

      {/* Notification tone (premium) */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>
          Notification Tone {!isPremium && <Text style={styles.premiumTag}>Premium</Text>}
        </Text>
        {(['normal', 'friendly_banter', 'harsh'] as const).map((tone) => (
          <Pressable
            key={tone}
            style={[
              styles.toneOption,
              prefs?.notification_tone === tone && styles.toneOptionSelected,
              !isPremium && tone !== 'normal' && styles.toneOptionLocked,
            ]}
            onPress={() => setTone(tone)}
          >
            <Text style={styles.toneLabel}>{TONE_LABELS[tone]}</Text>
            <Text style={styles.toneDesc}>{TONE_DESCS[tone]}</Text>
          </Pressable>
        ))}
      </View>

      {/* Danger zone */}
      <Pressable style={styles.signOutBtn} onPress={handleSignOut}>
        <Text style={styles.signOutBtnText}>Sign Out</Text>
      </Pressable>
    </ScrollView>
  );
}

function ToggleRow({
  label, value, onToggle,
}: { label: string; value: boolean; onToggle: (v: boolean) => void }) {
  return (
    <View style={styles.toggleRow}>
      <Text style={styles.toggleLabel}>{label}</Text>
      <Switch
        value={value}
        onValueChange={onToggle}
        trackColor={{ true: '#F5A623', false: '#333' }}
        thumbColor="#FFF"
      />
    </View>
  );
}

const TONE_LABELS = {
  normal: '🔔 Normal',
  friendly_banter: '😄 Friendly Banter',
  harsh: '💀 Harsh',
};

const TONE_DESCS = {
  normal: 'Standard reminders and updates',
  friendly_banter: 'Upbeat, playful messages',
  harsh: 'Blunt, no-nonsense accountability',
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  content: { padding: 20, paddingTop: 60, gap: 20, paddingBottom: 40 },
  userCard: {
    backgroundColor: '#111', borderRadius: 16, padding: 20, gap: 6,
    borderWidth: 1, borderColor: '#1A1A1A',
  },
  userName: { fontSize: 22, fontWeight: '800', color: '#FFF' },
  userEmail: { fontSize: 14, color: '#555' },
  tierBadge: {
    alignSelf: 'flex-start', backgroundColor: '#1A1A1A', borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 4, marginTop: 4,
  },
  tierBadgePremium: { backgroundColor: '#1A1200', borderWidth: 1, borderColor: '#F5A62350' },
  tierBadgeText: { color: '#F5A623', fontWeight: '700', fontSize: 12 },
  timezone: { fontSize: 13, color: '#555', marginTop: 4 },
  upgradeBtn: {
    backgroundColor: '#1A1200', borderRadius: 14, padding: 16,
    borderWidth: 1, borderColor: '#F5A62350', alignItems: 'center', gap: 4,
  },
  upgradeBtnText: { color: '#F5A623', fontSize: 16, fontWeight: '700' },
  upgradeBtnSub: { color: '#888', fontSize: 12 },
  section: { backgroundColor: '#111', borderRadius: 16, padding: 16, gap: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#FFF', marginBottom: 4 },
  premiumTag: { color: '#F5A623', fontSize: 12, fontWeight: '600' },
  toggleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  toggleLabel: { color: '#CCC', fontSize: 15 },
  toneOption: {
    backgroundColor: '#1A1A1A', borderRadius: 10, padding: 14,
    borderWidth: 1, borderColor: '#222',
  },
  toneOptionSelected: { borderColor: '#F5A623', backgroundColor: '#1A1200' },
  toneOptionLocked: { opacity: 0.4 },
  toneLabel: { color: '#FFF', fontSize: 15, fontWeight: '600', marginBottom: 2 },
  toneDesc: { color: '#666', fontSize: 12 },
  signOutBtn: {
    height: 52, backgroundColor: '#1A0A0A', borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
    borderWidth: 1, borderColor: '#E05A4E40',
  },
  signOutBtnText: { color: '#E05A4E', fontWeight: '600', fontSize: 15 },
});
