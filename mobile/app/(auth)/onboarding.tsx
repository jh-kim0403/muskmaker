/**
 * Onboarding screen — shown once after first sign-in.
 * Sets display name and confirms timezone.
 */
import { useState } from 'react';
import { View, Text, TextInput, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { router } from 'expo-router';
import { useUpdateProfile, useUpdateTimezone } from '@/api/hooks';
import { useAuthStore } from '@/stores/authStore';

export default function OnboardingScreen() {
  const [name, setName] = useState('');
  const [step, setStep] = useState<'name' | 'timezone'>('name');

  const { user, setUser } = useAuthStore();
  const updateProfile = useUpdateProfile();
  const updateTimezone = useUpdateTimezone();

  const deviceTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const handleNameNext = async () => {
    if (!name.trim()) return;
    const updated = await updateProfile.mutateAsync({ display_name: name.trim() });
    setUser(updated);
    setStep('timezone');
  };

  const handleFinish = async () => {
    try {
      // Confirm timezone — backend may have already set it from app launch
      await updateTimezone.mutateAsync(deviceTimezone);
    } catch {
      // May be rate limited if already set — fine to proceed
    }
    router.replace('/(tabs)');
  };

  if (step === 'name') {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>What should we call you?</Text>
        <TextInput
          style={styles.input}
          placeholder="Your name"
          placeholderTextColor="#555"
          value={name}
          onChangeText={setName}
          autoFocus
        />
        <Pressable
          style={[styles.button, !name.trim() && styles.buttonDisabled]}
          onPress={handleNameNext}
          disabled={!name.trim() || updateProfile.isPending}
        >
          {updateProfile.isPending
            ? <ActivityIndicator color="#000" />
            : <Text style={styles.buttonText}>Next</Text>
          }
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Confirm your timezone</Text>
      <Text style={styles.subtitle}>
        Your daily goals reset at midnight in your local timezone.
        Goals expire at the end of the day — make sure this is correct.
      </Text>
      <View style={styles.tzBox}>
        <Text style={styles.tzText}>{deviceTimezone}</Text>
      </View>
      <Text style={styles.tzNote}>
        You can change this later in Settings (limited to once per day).
      </Text>
      <Pressable style={styles.button} onPress={handleFinish} disabled={updateTimezone.isPending}>
        {updateTimezone.isPending
          ? <ActivityIndicator color="#000" />
          : <Text style={styles.buttonText}>Let's Go</Text>
        }
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A', padding: 32, justifyContent: 'center', gap: 20 },
  title: { fontSize: 30, fontWeight: '800', color: '#FFF' },
  subtitle: { fontSize: 15, color: '#888', lineHeight: 22 },
  input: {
    height: 56, backgroundColor: '#1A1A1A', borderRadius: 12,
    paddingHorizontal: 16, color: '#FFF', fontSize: 16,
  },
  button: {
    height: 56, backgroundColor: '#F5A623', borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
  },
  buttonDisabled: { opacity: 0.4 },
  buttonText: { color: '#000', fontSize: 16, fontWeight: '700' },
  tzBox: {
    backgroundColor: '#1A1A1A', borderRadius: 12, padding: 16,
    borderWidth: 1, borderColor: '#F5A623',
  },
  tzText: { color: '#F5A623', fontSize: 18, fontWeight: '600', textAlign: 'center' },
  tzNote: { fontSize: 13, color: '#555', textAlign: 'center' },
});
