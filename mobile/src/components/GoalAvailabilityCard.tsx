import { View, Text, StyleSheet, Pressable } from 'react-native';
import type { Goal } from '@/types/api';

interface Props {
  item: Goal;
  onPress: () => void;
}

export function GoalAvailabilityCard({ item, onPress }: Props) {
  const { status, goal_type } = item;

  const isActive = status === 'active';
  const isSubmitted = status === 'submitted';
  const isApproved = status === 'approved';
  const isRejected = status === 'rejected';
  const isExpired = status === 'expired';

  return (
    <Pressable
      style={[
        styles.card,
        isApproved && styles.cardApproved,
        isExpired && styles.cardExpired,
        isSubmitted && styles.cardPending,
      ]}
      onPress={isActive ? onPress : undefined}
      disabled={!isActive}
    >
      <View style={styles.left}>
        <Text style={styles.name}>{goal_type.name}</Text>
        <View style={styles.metaRow}>
          <Text style={styles.coins}>+{goal_type.coin_reward} coins</Text>
          <Text style={styles.difficulty}>{goal_type.difficulty}</Text>
        </View>
      </View>

      <View style={styles.right}>
        {isActive && (
          <View style={[styles.badge, styles.badgeActive]}>
            <Text style={styles.badgeText}>Verify →</Text>
          </View>
        )}
        {isSubmitted && (
          <View style={[styles.badge, styles.badgePending]}>
            <Text style={styles.badgePendingText}>Under Review</Text>
          </View>
        )}
        {isApproved && (
          <View style={[styles.badge, styles.badgeDone]}>
            <Text style={styles.badgeDoneText}>✓ Done</Text>
          </View>
        )}
        {isRejected && (
          <View style={[styles.badge, styles.badgeRejected]}>
            <Text style={styles.badgeRejectedText}>Rejected</Text>
          </View>
        )}
        {isExpired && (
          <View style={[styles.badge, styles.badgeExpired]}>
            <Text style={styles.badgeExpiredText}>Missed</Text>
          </View>
        )}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#111', borderRadius: 14, padding: 16,
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    borderWidth: 1, borderColor: '#1A1A1A',
  },
  cardApproved: { borderColor: '#2A4A2A', backgroundColor: '#0A140A' },
  cardExpired: { opacity: 0.4 },
  cardPending: { borderColor: '#2A2A1A' },
  left: { flex: 1, gap: 6 },
  name: { fontSize: 17, fontWeight: '700', color: '#FFF' },
  metaRow: { flexDirection: 'row', gap: 8 },
  coins: { fontSize: 13, color: '#F5A623', fontWeight: '600' },
  difficulty: { fontSize: 13, color: '#555' },
  right: { marginLeft: 12 },
  badge: {
    backgroundColor: '#1A1A1A', borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 6,
  },
  badgeText: { color: '#FFF', fontSize: 13, fontWeight: '600' },
  badgeActive: { backgroundColor: '#F5A62320', borderWidth: 1, borderColor: '#F5A623' },
  badgePending: { backgroundColor: '#1A1A0A' },
  badgePendingText: { color: '#AAA820', fontSize: 12, fontWeight: '600' },
  badgeDone: { backgroundColor: '#0A1A0A' },
  badgeDoneText: { color: '#6AB06A', fontSize: 13, fontWeight: '600' },
  badgeRejected: { backgroundColor: '#1A0A0A' },
  badgeRejectedText: { color: '#E05555', fontSize: 12, fontWeight: '600' },
  badgeExpired: { backgroundColor: '#1A0A0A' },
  badgeExpiredText: { color: '#666', fontSize: 12 },
});
