/**
 * Goal creation screen (modal).
 *
 * Pre-fills the goal type if goalTypeId is passed as a query param.
 * After creation, navigates directly to the camera for verification.
 */
import { useState } from 'react';
import {
  View, Text, StyleSheet, Pressable, TextInput, ActivityIndicator, Alert,
} from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import dayjs from 'dayjs';

import { useGoalTypes, useCreateGoal } from '@/api/hooks';
import { useAuthStore } from '@/stores/authStore';

export default function CreateGoalScreen() {
  const { goalTypeId } = useLocalSearchParams<{ goalTypeId?: string }>();
  const { data: goalTypes } = useGoalTypes();
  const createGoal = useCreateGoal();
  const isPremium = useAuthStore((s) => s.isPremium)();
  const userTz = useAuthStore((s) => s.timezone)();

  const [notes, setNotes] = useState('');

  const selectedType = goalTypes?.find((t) => t.id === goalTypeId);

  const expiryTime = dayjs().tz(userTz).endOf('day').format('h:mm A');

  const handleCreate = async () => {
    if (!goalTypeId) return;
    try {
      const goal = await createGoal.mutateAsync({ goal_type_id: goalTypeId, notes: notes || undefined });

      // Navigate to camera immediately after goal creation
      router.replace(`/verification/camera?goalId=${goal.id}`);
    } catch (err: any) {
      Alert.alert(
        'Could not create goal',
        err.detail ?? 'Please try again',
        [{ text: 'OK' }]
      );
    }
  };

  if (!selectedType) {
    return (
      <View style={styles.container}>
        <Text style={styles.errorText}>Goal type not found.</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <Pressable style={styles.closeBtn} onPress={() => router.back()}>
        <Text style={styles.closeBtnText}>✕</Text>
      </Pressable>

      <Text style={styles.title}>{selectedType.name}</Text>

      <View style={styles.metaRow}>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>+{selectedType.coin_reward} coins on completion</Text>
        </View>
        <View style={[styles.badge, styles.difficultyBadge]}>
          <Text style={styles.badgeText}>{selectedType.difficulty}</Text>
        </View>
      </View>

      {selectedType.description && (
        <Text style={styles.description}>{selectedType.description}</Text>
      )}

      {/* Expiry warning */}
      <View style={styles.expiryBox}>
        <Text style={styles.expiryText}>
          ⚠ This goal must be verified before {expiryTime} tonight.
          It cannot be verified on a different day.
        </Text>
      </View>

      {/* Verification path info */}
      <View style={styles.infoBox}>
        {isPremium ? (
          <Text style={styles.infoText}>
            ✨ Premium: instant AI verification after photo
            {selectedType.supports_location_path ? ' (1-photo with location available)' : ''}
          </Text>
        ) : (
          <Text style={styles.infoText}>
            📋 Free: 2 photos required · manual review · up to 24 hours
          </Text>
        )}
      </View>

      <TextInput
        style={styles.notes}
        placeholder="Optional notes about your goal..."
        placeholderTextColor="#555"
        value={notes}
        onChangeText={setNotes}
        multiline
        maxLength={200}
      />

      <Pressable
        style={styles.createButton}
        onPress={handleCreate}
        disabled={createGoal.isPending}
      >
        {createGoal.isPending
          ? <ActivityIndicator color="#000" />
          : <Text style={styles.createButtonText}>Create Goal & Start Camera</Text>
        }
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A', padding: 24, paddingTop: 60 },
  closeBtn: { position: 'absolute', top: 60, right: 24, zIndex: 10 },
  closeBtnText: { color: '#888', fontSize: 20 },
  title: { fontSize: 28, fontWeight: '800', color: '#FFF', marginBottom: 12 },
  metaRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  badge: {
    backgroundColor: '#1A1A1A', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4,
    borderWidth: 1, borderColor: '#F5A62360',
  },
  difficultyBadge: { borderColor: '#55555560' },
  badgeText: { color: '#F5A623', fontSize: 13, fontWeight: '600' },
  description: { color: '#888', fontSize: 15, lineHeight: 22, marginBottom: 16 },
  expiryBox: {
    backgroundColor: '#1A0A00', borderRadius: 10, padding: 12,
    borderWidth: 1, borderColor: '#F5A62340', marginBottom: 12,
  },
  expiryText: { color: '#F5A623', fontSize: 13, lineHeight: 18 },
  infoBox: {
    backgroundColor: '#0A1A0A', borderRadius: 10, padding: 12,
    borderWidth: 1, borderColor: '#2A4A2A', marginBottom: 20,
  },
  infoText: { color: '#6AB06A', fontSize: 13, lineHeight: 18 },
  notes: {
    backgroundColor: '#1A1A1A', borderRadius: 12, padding: 14,
    color: '#FFF', fontSize: 15, minHeight: 80, marginBottom: 24,
    textAlignVertical: 'top',
  },
  createButton: {
    backgroundColor: '#F5A623', borderRadius: 12, height: 56,
    justifyContent: 'center', alignItems: 'center',
  },
  createButtonText: { color: '#000', fontSize: 16, fontWeight: '700' },
  errorText: { color: '#888', textAlign: 'center', marginTop: 100 },
});
