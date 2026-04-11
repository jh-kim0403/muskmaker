/**
 * Sweepstakes tab — enter and track odds.
 *
 * Shows:
 *  - Active sweepstakes with prize description
 *  - User's entered coins and estimated odds
 *  - Total pool size (all users)
 *  - Entry flow with coin spend input
 *  - Apple compliance text (always visible)
 */
import { useState } from 'react';
import {
  View, Text, StyleSheet, Pressable, FlatList, Modal,
  TextInput, Alert, ActivityIndicator,
} from 'react-native';
import { router } from 'expo-router';

import { useActiveSweepstakes, useEnterSweepstakes } from '@/api/hooks';
import { useAuthStore } from '@/stores/authStore';
import { OddsDisplay } from '@/components/OddsDisplay';
import type { SweepstakesWithOdds } from '@/types/api';

export default function SweepstakesTab() {
  const { data: sweepstakes, isLoading, refetch } = useActiveSweepstakes();
  const coinBalance = useAuthStore((s) => s.coinBalance)();
  const enterSweepstakes = useEnterSweepstakes();

  const [selectedSweep, setSelectedSweep] = useState<SweepstakesWithOdds | null>(null);
  const [coinsToSpend, setCoinsToSpend] = useState('');

  const handleEnter = async () => {
    const coins = parseInt(coinsToSpend, 10);
    if (isNaN(coins) || coins <= 0) {
      Alert.alert('Invalid amount', 'Please enter a valid number of coins.');
      return;
    }
    if (coins > coinBalance) {
      Alert.alert('Not enough coins', `You have ${coinBalance} coins.`);
      return;
    }
    if (!selectedSweep) return;

    try {
      const result = await enterSweepstakes.mutateAsync({
        sweepstakes_id: selectedSweep.id,
        coins_to_spend: coins,
      });
      setSelectedSweep(null);
      setCoinsToSpend('');
      Alert.alert(
        'Entered!',
        `You entered ${result.coins_entered} coin(s).\nNew odds: ${formatOdds(result.estimated_odds)}`
      );
    } catch (err: any) {
      Alert.alert('Entry failed', err.detail ?? 'Please try again');
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Sweepstakes</Text>
        <View style={styles.balanceBadge}>
          <Text style={styles.balanceAmount}>{coinBalance}</Text>
          <Text style={styles.balanceLabel}>coins available</Text>
        </View>
      </View>

      {/* Apple compliance disclaimer — always visible */}
      <View style={styles.disclaimer}>
        <Text style={styles.disclaimerText}>
          No purchase necessary. Sponsored by MuskMaker. Apple is not a sponsor.
          Odds depend on total eligible entries. Open to eligible residents only.
        </Text>
      </View>

      <FlatList
        data={sweepstakes ?? []}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <SweepstakesCard
            sweep={item}
            onEnter={() => setSelectedSweep(item)}
          />
        )}
        contentContainerStyle={styles.list}
        refreshing={isLoading}
        onRefresh={refetch}
        ListEmptyComponent={
          !isLoading ? <Text style={styles.empty}>No active sweepstakes right now.</Text> : null
        }
      />

      {/* Entry modal */}
      <Modal
        visible={!!selectedSweep}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setSelectedSweep(null)}
      >
        {selectedSweep && (
          <View style={styles.modal}>
            <Text style={styles.modalTitle}>{selectedSweep.prize_description}</Text>

            <OddsDisplay
              userEntries={selectedSweep.user_entries}
              totalEntries={selectedSweep.total_entries_count}
              estimatedOdds={selectedSweep.estimated_odds}
            />

            <Text style={styles.modalLabel}>Coins to spend (= entries to add)</Text>
            <TextInput
              style={styles.coinsInput}
              value={coinsToSpend}
              onChangeText={setCoinsToSpend}
              keyboardType="number-pad"
              placeholder={`Max ${coinBalance}`}
              placeholderTextColor="#555"
              autoFocus
            />
            <Text style={styles.balanceHint}>You have {coinBalance} coins available</Text>

            <Pressable
              style={[styles.enterBtn, enterSweepstakes.isPending && styles.btnDisabled]}
              onPress={handleEnter}
              disabled={enterSweepstakes.isPending}
            >
              {enterSweepstakes.isPending
                ? <ActivityIndicator color="#000" />
                : <Text style={styles.enterBtnText}>Enter Sweepstakes</Text>
              }
            </Pressable>

            <Pressable onPress={() => setSelectedSweep(null)} style={styles.cancelModal}>
              <Text style={styles.cancelModalText}>Cancel</Text>
            </Pressable>

            <Text style={styles.fairnessNote}>
              1 coin = 1 entry for all users. Subscription status has no effect on odds.
              No purchase necessary to win.
            </Text>
          </View>
        )}
      </Modal>
    </View>
  );
}

function SweepstakesCard({
  sweep, onEnter,
}: { sweep: SweepstakesWithOdds; onEnter: () => void }) {
  return (
    <View style={cardStyles.card}>
      <Text style={cardStyles.prize}>{sweep.prize_description}</Text>

      <OddsDisplay
        userEntries={sweep.user_entries}
        totalEntries={sweep.total_entries_count}
        estimatedOdds={sweep.estimated_odds}
        compact
      />

      <Pressable style={cardStyles.enterBtn} onPress={onEnter}>
        <Text style={cardStyles.enterBtnText}>Enter with Coins</Text>
      </Pressable>
    </View>
  );
}

function formatOdds(odds: number | null): string {
  if (odds === null || odds === 0) return 'N/A';
  if (odds < 0.0001) return '< 0.01%';
  return `${(odds * 100).toFixed(2)}%`;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 20, paddingTop: 60,
  },
  title: { fontSize: 28, fontWeight: '800', color: '#FFF' },
  balanceBadge: { alignItems: 'center' },
  balanceAmount: { fontSize: 22, fontWeight: '800', color: '#F5A623' },
  balanceLabel: { fontSize: 11, color: '#888' },
  disclaimer: {
    marginHorizontal: 20, marginBottom: 8,
    backgroundColor: '#0A0A14', borderRadius: 8, padding: 10,
    borderWidth: 1, borderColor: '#1A1A2A',
  },
  disclaimerText: { color: '#444', fontSize: 11, lineHeight: 16, textAlign: 'center' },
  list: { padding: 20, gap: 16 },
  empty: { color: '#555', textAlign: 'center', marginTop: 40, fontSize: 15 },
  modal: { flex: 1, backgroundColor: '#0A0A0A', padding: 24, paddingTop: 40, gap: 16 },
  modalTitle: { fontSize: 22, fontWeight: '800', color: '#FFF' },
  modalLabel: { color: '#888', fontSize: 14 },
  coinsInput: {
    height: 56, backgroundColor: '#1A1A1A', borderRadius: 12,
    paddingHorizontal: 16, color: '#FFF', fontSize: 22, fontWeight: '700',
  },
  balanceHint: { color: '#555', fontSize: 13 },
  enterBtn: {
    height: 56, backgroundColor: '#F5A623', borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
  },
  btnDisabled: { opacity: 0.4 },
  enterBtnText: { color: '#000', fontWeight: '700', fontSize: 16 },
  cancelModal: { alignItems: 'center' },
  cancelModalText: { color: '#555', fontSize: 15 },
  fairnessNote: { color: '#333', fontSize: 11, textAlign: 'center', lineHeight: 16, marginTop: 8 },
});

const cardStyles = StyleSheet.create({
  card: {
    backgroundColor: '#111', borderRadius: 16, padding: 20, gap: 12,
    borderWidth: 1, borderColor: '#1A1A1A',
  },
  prize: { fontSize: 20, fontWeight: '800', color: '#FFF' },
  enterBtn: {
    height: 48, backgroundColor: '#F5A623', borderRadius: 10,
    justifyContent: 'center', alignItems: 'center',
  },
  enterBtnText: { color: '#000', fontWeight: '700', fontSize: 15 },
});
