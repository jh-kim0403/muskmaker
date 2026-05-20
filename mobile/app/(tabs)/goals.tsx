import { useState } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  Pressable,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';

import { useFutureGoals, usePastGoals } from '@/api/hooks';
import type { Goal } from '@/types/api';

type GoalListMode = 'past' | 'future';

const STATUS_LABELS: Record<Goal['status'], string> = {
  active: 'Active',
  submitted: 'Under Review',
  approved: 'Done',
  rejected: 'Rejected',
  expired: 'Missed',
};

function formatGoalDate(value: string) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function GoalHistoryCard({ goal }: { goal: Goal }) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={styles.cardTitleWrap}>
          <Text style={styles.goalTitle} numberOfLines={1}>
            {goal.title || goal.goal_type.name}
          </Text>
          <Text style={styles.goalDate}>{formatGoalDate(goal.local_goal_date)}</Text>
        </View>
        <View style={[styles.statusBadge, styles[`status_${goal.status}`]]}>
          <Text style={[styles.statusText, styles[`statusText_${goal.status}`]]}>
            {STATUS_LABELS[goal.status]}
          </Text>
        </View>
      </View>

      <View style={styles.metaRow}>
        <Text style={styles.goalType}>{goal.goal_type.name}</Text>
        <Text style={styles.metaDot}>•</Text>
        <Text style={styles.coins}>+{goal.goal_type.coin_reward} coins</Text>
        <Text style={styles.metaDot}>•</Text>
        <Text style={styles.difficulty}>{goal.goal_type.difficulty}</Text>
      </View>
    </View>
  );
}

export default function GoalsScreen() {
  const [mode, setMode] = useState<GoalListMode>('past');

  const pastGoals = usePastGoals();
  const futureGoals = useFutureGoals();
  const activeQuery = mode === 'past' ? pastGoals : futureGoals;
  const goals = activeQuery.data ?? [];

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.heading}>Goals</Text>
        <View style={styles.segmentedControl}>
          <Pressable
            style={[styles.segmentButton, mode === 'past' && styles.segmentButtonActive]}
            onPress={() => setMode('past')}
          >
            <Text style={[styles.segmentText, mode === 'past' && styles.segmentTextActive]}>
              Past Goals
            </Text>
          </Pressable>
          <Pressable
            style={[styles.segmentButton, mode === 'future' && styles.segmentButtonActive]}
            onPress={() => setMode('future')}
          >
            <Text style={[styles.segmentText, mode === 'future' && styles.segmentTextActive]}>
              Future Goals
            </Text>
          </Pressable>
        </View>
      </View>

      {activeQuery.isLoading ? (
        <ActivityIndicator color="#F5A623" style={styles.loading} />
      ) : (
        <FlatList
          data={goals}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => <GoalHistoryCard goal={item} />}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={activeQuery.isRefetching}
              onRefresh={activeQuery.refetch}
              tintColor="#F5A623"
            />
          }
          ListEmptyComponent={
            <Text style={styles.emptyText}>
              {mode === 'past' ? 'No past goals yet.' : 'No future goals scheduled.'}
            </Text>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  header: { padding: 20, paddingTop: 60, gap: 18 },
  heading: { fontSize: 26, fontWeight: '800', color: '#FFF' },
  segmentedControl: {
    flexDirection: 'row',
    backgroundColor: '#111',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#222',
    padding: 4,
  },
  segmentButton: {
    flex: 1,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
  },
  segmentButtonActive: { backgroundColor: '#F5A623' },
  segmentText: { color: '#888', fontSize: 14, fontWeight: '700' },
  segmentTextActive: { color: '#000' },
  loading: { marginTop: 40 },
  list: { paddingHorizontal: 20, paddingBottom: 32, gap: 12 },
  emptyText: { color: '#555', textAlign: 'center', marginTop: 40, fontSize: 15 },
  card: {
    backgroundColor: '#111',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#1A1A1A',
    gap: 12,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  },
  cardTitleWrap: { flex: 1, gap: 4 },
  goalTitle: { fontSize: 17, fontWeight: '800', color: '#FFF' },
  goalDate: { fontSize: 13, color: '#888' },
  metaRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 7 },
  goalType: { fontSize: 13, color: '#AAA', fontWeight: '600' },
  metaDot: { color: '#444', fontSize: 13 },
  coins: { fontSize: 13, color: '#F5A623', fontWeight: '700' },
  difficulty: { fontSize: 13, color: '#666' },
  statusBadge: {
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: '#1A1A1A',
  },
  statusText: { fontSize: 12, fontWeight: '800' },
  status_active: { backgroundColor: '#F5A62320', borderWidth: 1, borderColor: '#F5A623' },
  status_submitted: { backgroundColor: '#1A1A0A' },
  status_approved: { backgroundColor: '#0A1A0A' },
  status_rejected: { backgroundColor: '#1A0A0A' },
  status_expired: { backgroundColor: '#171717' },
  statusText_active: { color: '#F5A623' },
  statusText_submitted: { color: '#AAA820' },
  statusText_approved: { color: '#6AB06A' },
  statusText_rejected: { color: '#E05555' },
  statusText_expired: { color: '#777' },
});
