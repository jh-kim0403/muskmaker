import { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  TextInput,
  ActivityIndicator,
  Alert,
  ScrollView,
  FlatList,
} from 'react-native';
import { router } from 'expo-router';
import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

import { useGoalTypes, useCreateGoal } from '@/api/hooks';
import { useAuthStore } from '@/stores/authStore';
import type { GoalType } from '@/types/api';

dayjs.extend(utc);
dayjs.extend(timezone);

// ── Date helpers ──────────────────────────────────────────────────────────────

function buildDateOptions(userTz: string) {
  const today = dayjs().tz(userTz);
  return Array.from({ length: 7 }, (_, i) => {
    const d = today.add(i, 'day');
    return {
      label: i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : d.format('ddd D'),
      sublabel: i <= 1 ? d.format('MMM D') : d.format('MMM'),
      value: d.format('YYYY-MM-DD'),
    };
  });
}

// ── Main screen ───────────────────────────────────────────────────────────────

export default function CreateGoalScreen() {
  const { data: goalTypes, isLoading: typesLoading } = useGoalTypes();
  const createGoal = useCreateGoal();
  const userTz = useAuthStore((s) => s.timezone)();

  const dateOptions = buildDateOptions(userTz);

  const [selectedType, setSelectedType] = useState<GoalType | null>(null);
  const [title, setTitle] = useState('');
  const [selectedDate, setSelectedDate] = useState(dateOptions[0].value);

  const canSubmit = !!selectedType && title.trim().length > 0;

  const handleCreate = async () => {
    if (!selectedType || !title.trim()) return;
    try {
      await createGoal.mutateAsync({
        goal_type_id: selectedType.id,
        title: title.trim(),
        expire_user_local_date: selectedDate,
      });
      router.replace('/(tabs)');
      Alert.alert('Goal Created!', `"${title.trim()}" has been added to today's goals.`, [{ text: 'OK' }]);
    } catch (err: any) {
      Alert.alert('Could not create goal', err.detail ?? 'Please try again', [{ text: 'OK' }]);
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.closeBtn}>
          <Text style={styles.closeBtnText}>✕</Text>
        </Pressable>
        <Text style={styles.heading}>New Goal</Text>
      </View>

      {/* ── Goal Type ── */}
      <Text style={styles.label}>Type of Goal</Text>
      {typesLoading ? (
        <ActivityIndicator color="#F5A623" style={{ marginVertical: 16 }} />
      ) : (
        <View style={styles.typeGrid}>
          {(goalTypes ?? []).map((gt) => {
            const active = selectedType?.id === gt.id;
            return (
              <Pressable
                key={gt.id}
                style={[styles.typeCard, active && styles.typeCardActive]}
                onPress={() => {
                  setSelectedType(gt);
                  if (!title) setTitle(gt.name);
                }}
              >
                <Text style={[styles.typeName, active && styles.typeNameActive]} numberOfLines={2}>
                  {gt.name}
                </Text>
                <Text style={styles.typeCoins}>+{gt.coin_reward} coins</Text>
              </Pressable>
            );
          })}
        </View>
      )}

      {/* ── Title ── */}
      <Text style={styles.label}>Title</Text>
      <TextInput
        style={styles.input}
        placeholder="e.g. Hit the gym for 45 min"
        placeholderTextColor="#555"
        value={title}
        onChangeText={setTitle}
        maxLength={100}
        returnKeyType="done"
      />

      {/* ── Deadline ── */}
      <Text style={styles.label}>Deadline</Text>
      <FlatList
        data={dateOptions}
        keyExtractor={(d) => d.value}
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.dateRow}
        renderItem={({ item }) => {
          const active = item.value === selectedDate;
          return (
            <Pressable
              style={[styles.dateChip, active && styles.dateChipActive]}
              onPress={() => setSelectedDate(item.value)}
            >
              <Text style={[styles.dateChipLabel, active && styles.dateChipLabelActive]}>
                {item.label}
              </Text>
              <Text style={[styles.dateChipSub, active && styles.dateChipSubActive]}>
                {item.sublabel}
              </Text>
            </Pressable>
          );
        }}
      />

      {/* ── Submit ── */}
      <Pressable
        style={[styles.createBtn, !canSubmit && styles.createBtnDisabled]}
        onPress={handleCreate}
        disabled={!canSubmit || createGoal.isPending}
      >
        {createGoal.isPending ? (
          <ActivityIndicator color="#000" />
        ) : (
          <Text style={styles.createBtnText}>Create Goal</Text>
        )}
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  content: { padding: 24, paddingTop: 60, paddingBottom: 48 },

  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 32 },
  closeBtn: { marginRight: 16 },
  closeBtnText: { color: '#888', fontSize: 20 },
  heading: { fontSize: 26, fontWeight: '800', color: '#FFF' },

  label: { fontSize: 12, color: '#888', fontWeight: '600', letterSpacing: 0.8, marginBottom: 10, marginTop: 24 },

  // Goal type grid
  typeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  typeCard: {
    width: '47%',
    backgroundColor: '#111',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#222',
    gap: 6,
  },
  typeCardActive: { borderColor: '#F5A623', backgroundColor: '#1A1200' },
  typeName: { fontSize: 15, fontWeight: '700', color: '#AAA', lineHeight: 20 },
  typeNameActive: { color: '#FFF' },
  typeCoins: { fontSize: 12, color: '#F5A623', fontWeight: '600' },

  // Title input
  input: {
    backgroundColor: '#111',
    borderRadius: 12,
    padding: 14,
    color: '#FFF',
    fontSize: 15,
    borderWidth: 1,
    borderColor: '#222',
  },

  // Date chips
  dateRow: { gap: 8, paddingVertical: 4 },
  dateChip: {
    backgroundColor: '#111',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#222',
    alignItems: 'center',
    minWidth: 72,
  },
  dateChipActive: { backgroundColor: '#1A1200', borderColor: '#F5A623' },
  dateChipLabel: { fontSize: 14, fontWeight: '700', color: '#AAA' },
  dateChipLabelActive: { color: '#F5A623' },
  dateChipSub: { fontSize: 11, color: '#555', marginTop: 2 },
  dateChipSubActive: { color: '#F5A62399' },

  // Create button
  createBtn: {
    backgroundColor: '#F5A623',
    borderRadius: 14,
    height: 56,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 36,
  },
  createBtnDisabled: { opacity: 0.35 },
  createBtnText: { color: '#000', fontSize: 16, fontWeight: '800' },
});
