/**
 * Home tab — Today's goals.
 *
 * Shows:
 *  - User's coin balance
 *  - All active goal types with today's availability
 *  - "Already done today" state for completed types
 *  - Daily reset time ("Resets at midnight your time")
 *  - CTA to create a new goal
 */
import { View, Text, FlatList, StyleSheet, Pressable, RefreshControl } from 'react-native';
import { router } from 'expo-router';
import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

import { useTodaysGoals } from '@/api/hooks';
import { useAuthStore } from '@/stores/authStore';
import { GoalAvailabilityCard } from '@/components/GoalAvailabilityCard';

dayjs.extend(utc);
dayjs.extend(timezone);

export default function TodayScreen() {
  const user = useAuthStore((s) => s.user);
  const isPremium = user?.subscription_tier === 'premium';
  const coinBalance = useAuthStore((s) => s.coinBalance)();

  const { data: goals, isLoading, refetch, isRefetching } = useTodaysGoals();

  // Show when the user's local day ends
  const userTz = user?.timezone ?? 'UTC';
  const resetTime = dayjs().tz(userTz).endOf('day').format('h:mm A');

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.greeting}>
            Hey {user?.display_name?.split(' ')[0] ?? 'there'} 👋
          </Text>
          <Text style={styles.resetHint}>Goals reset at midnight · {resetTime} tonight</Text>
        </View>
        <Pressable
          style={styles.coinBadge}
          onPress={() => router.push('/(tabs)/sweepstakes')}
        >
          <Text style={styles.coinAmount}>{coinBalance}</Text>
          <Text style={styles.coinLabel}>coins</Text>
        </Pressable>
      </View>

      {/* Premium badge */}
      {!isPremium && (
        <Pressable style={styles.premiumBanner} onPress={() => router.push('/paywall')}>
          <Text style={styles.premiumBannerText}>
            ✨ Go Premium — instant verification, no ads, custom notifications
          </Text>
        </Pressable>
      )}

      {/* Create goal CTA */}
      <Pressable style={styles.createBtn} onPress={() => router.push('/goals/create')}>
        <Text style={styles.createBtnText}>+ Create New Goal</Text>
      </Pressable>

      {/* Goal list */}
      <FlatList
        data={goals ?? []}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <GoalAvailabilityCard
            item={item}
            onPress={() => router.push(`/verification/camera?goalId=${item.id}`)}
          />
        )}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={refetch}
            tintColor="#F5A623"
          />
        }
        ListEmptyComponent={
          isLoading ? null : (
            <Text style={styles.emptyText}>No goals available today.</Text>
          )
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start',
    padding: 20, paddingTop: 60,
  },
  greeting: { fontSize: 24, fontWeight: '800', color: '#FFF' },
  resetHint: { fontSize: 13, color: '#555', marginTop: 4 },
  coinBadge: {
    backgroundColor: '#1A1A1A', borderRadius: 12, padding: 12,
    alignItems: 'center', borderWidth: 1, borderColor: '#F5A623',
  },
  coinAmount: { fontSize: 22, fontWeight: '800', color: '#F5A623' },
  coinLabel: { fontSize: 11, color: '#888', marginTop: 2 },
  premiumBanner: {
    marginHorizontal: 20, marginBottom: 8,
    backgroundColor: '#1A1200', borderRadius: 10, padding: 12,
    borderWidth: 1, borderColor: '#F5A62350',
  },
  premiumBannerText: { color: '#F5A623', fontSize: 13, textAlign: 'center' },
  list: { paddingHorizontal: 20, paddingBottom: 32, gap: 12 },
  emptyText: { color: '#555', textAlign: 'center', marginTop: 40, fontSize: 15 },
  createBtn: {
    marginHorizontal: 20, marginBottom: 12,
    backgroundColor: '#F5A623', borderRadius: 12, padding: 14, alignItems: 'center',
  },
  createBtnText: { color: '#000', fontSize: 15, fontWeight: '700' },
});
