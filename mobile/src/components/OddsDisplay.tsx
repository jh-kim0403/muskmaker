/**
 * OddsDisplay — shows sweepstakes odds to the user.
 *
 * Always shows:
 *  - User's entered coins
 *  - Total pool (all users)
 *  - Estimated probability
 *
 * Compact variant for the sweepstakes card list.
 * Full variant for the entry modal.
 *
 * Important: odds are always clearly labeled as estimates based on current pool.
 * They change as more users enter.
 */
import { View, Text, StyleSheet } from 'react-native';

interface Props {
  userEntries: number;
  totalEntries: number;
  estimatedOdds: number | null;
  compact?: boolean;
}

export function OddsDisplay({ userEntries, totalEntries, estimatedOdds, compact }: Props) {
  const oddsText = formatOdds(estimatedOdds);
  const poolText = totalEntries.toLocaleString();
  const userText = userEntries.toLocaleString();

  if (compact) {
    return (
      <View style={styles.compactRow}>
        <Text style={styles.compactItem}>
          <Text style={styles.highlight}>{userText}</Text>
          <Text style={styles.muted}> / {poolText} entries</Text>
        </Text>
        <Text style={styles.compactOdds}>{oddsText}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Row label="Your entries" value={userText} />
      <Row label="Total pool" value={poolText} />
      <View style={styles.oddsRow}>
        <Text style={styles.oddsLabel}>Estimated odds</Text>
        <Text style={styles.oddsValue}>{oddsText}</Text>
      </View>
      <Text style={styles.disclaimer}>
        Odds update as more users enter. Based on current total pool.
      </Text>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

function formatOdds(odds: number | null): string {
  if (odds === null || odds === 0) return 'No entries yet';
  if (odds >= 1) return '100%';
  if (odds < 0.0001) return '< 0.01%';
  return `${(odds * 100).toFixed(2)}%`;
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#0A0A14', borderRadius: 10, padding: 14, gap: 10,
    borderWidth: 1, borderColor: '#1A1A2A',
  },
  row: { flexDirection: 'row', justifyContent: 'space-between' },
  rowLabel: { color: '#666', fontSize: 14 },
  rowValue: { color: '#CCC', fontSize: 14, fontWeight: '600' },
  oddsRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingTop: 8, borderTopWidth: 1, borderTopColor: '#1A1A2A',
  },
  oddsLabel: { color: '#888', fontSize: 14 },
  oddsValue: { color: '#F5A623', fontSize: 22, fontWeight: '800' },
  disclaimer: { color: '#333', fontSize: 11, lineHeight: 16 },
  // Compact
  compactRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  compactItem: { fontSize: 13 },
  highlight: { color: '#F5A623', fontWeight: '700' },
  muted: { color: '#555' },
  compactOdds: { color: '#F5A623', fontWeight: '700', fontSize: 14 },
});
