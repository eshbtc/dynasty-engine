import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import useSWR from 'swr';
import { getPnl, getSummary } from '../lib/api';

export default function Dashboard() {
  const { data: pnl } = useSWR('pnl', getPnl, { refreshInterval: 15000 });
  const { data: daily } = useSWR('summary', getSummary, { refreshInterval: 60000 });

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Live PnL</Text>
      <Text style={styles.pnl}>{pnl ?? '…'}</Text>

      {daily && (
        <View style={{ marginTop: 24 }}>
          <Text style={styles.subtitle}>Today</Text>
          <Text>{JSON.stringify(daily[0] || {}, null, 2)}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 16 },
  title: { fontSize: 24, fontWeight: '600' },
  pnl: { fontSize: 32, marginTop: 8 },
  subtitle: { fontSize: 18, marginTop: 16 },
});
