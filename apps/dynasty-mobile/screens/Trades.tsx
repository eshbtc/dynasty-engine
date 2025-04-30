import React from 'react';
import { View, Text, FlatList, StyleSheet } from 'react-native';
import useSWR from 'swr';
import { getEpisodes } from '../lib/api';

export default function Trades() {
  const { data: rows } = useSWR('episodes', () => getEpisodes(100), { refreshInterval: 10000 });

  return (
    <View style={styles.container}>
      <FlatList
        data={rows || []}
        keyExtractor={(_, idx) => String(idx)}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text>{item.symbol}</Text>
            <Text>{item.action}</Text>
            <Text>{item.price}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 12 },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
});
