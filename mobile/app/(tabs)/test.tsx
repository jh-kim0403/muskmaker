import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { apiClient } from '@/api/client';

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE';

const PRESETS: { label: string; method: Method; path: string; body?: string }[] = [
  { label: 'GET /users/me', method: 'GET', path: '/users/me' },
  { label: 'GET /goals/types', method: 'GET', path: '/goals/types' },
  { label: 'GET /goals/today', method: 'GET', path: '/goals/today' },
  { label: 'GET /sweepstakes/active', method: 'GET', path: '/sweepstakes/active' },
  { label: 'GET /sweepstakes/my/wins', method: 'GET', path: '/sweepstakes/my/wins' },
  {
    label: 'POST /users/me/complete-onboarding',
    method: 'POST',
    path: '/users/me/complete-onboarding',
  },
  {
    label: 'PATCH /users/me',
    method: 'PATCH',
    path: '/users/me',
    body: '{"display_name": "Test"}',
  },
  {
    label: 'POST /goals/new',
    method: 'POST',
    path: '/goals/new',
    body: JSON.stringify(
      {
        goal_type_id: 'f11826bb-eb1b-4941-98d0-58ad6b25cce0',
        title: 'Go to the gym',
        expire_user_local_date: new Date().toISOString().split('T')[0],
      },
      null,
      2
    ),
  },
];

export default function TestScreen() {
  const [method, setMethod] = useState<Method>('GET');
  const [path, setPath] = useState('/users/me');
  const [body, setBody] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ status?: number; data?: unknown; error?: unknown } | null>(
    null
  );

  const applyPreset = (preset: (typeof PRESETS)[number]) => {
    setMethod(preset.method);
    setPath(preset.path);
    setBody(preset.body ?? '');
    setResult(null);
  };

  const call = async () => {
    setLoading(true);
    setResult(null);
    try {
      let parsedBody: unknown = undefined;
      if (body.trim()) {
        try {
          parsedBody = JSON.parse(body);
        } catch {
          setResult({ error: 'Invalid JSON body' });
          setLoading(false);
          return;
        }
      }

      const res = await apiClient.request({ method, url: path, data: parsedBody });
      setResult({ status: res.status, data: res.data });
    } catch (err: unknown) {
      setResult({ error: err });
    } finally {
      setLoading(false);
    }
  };

  const methods: Method[] = ['GET', 'POST', 'PATCH', 'DELETE'];

  return (
    <ScrollView style={styles.container} keyboardShouldPersistTaps="handled">
      <Text style={styles.heading}>API Tester</Text>

      {/* Presets */}
      <Text style={styles.label}>Presets</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.presetRow}>
        {PRESETS.map((p) => (
          <TouchableOpacity key={p.label} style={styles.presetChip} onPress={() => applyPreset(p)}>
            <Text style={styles.presetText}>{p.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Method */}
      <Text style={styles.label}>Method</Text>
      <View style={styles.methodRow}>
        {methods.map((m) => (
          <TouchableOpacity
            key={m}
            style={[styles.methodBtn, method === m && styles.methodBtnActive]}
            onPress={() => setMethod(m)}
          >
            <Text style={[styles.methodText, method === m && styles.methodTextActive]}>{m}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Path */}
      <Text style={styles.label}>Path</Text>
      <TextInput
        style={styles.input}
        value={path}
        onChangeText={setPath}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="/users/me"
        placeholderTextColor="#555"
      />

      {/* Body */}
      <Text style={styles.label}>Body (JSON)</Text>
      <TextInput
        style={[styles.input, styles.bodyInput]}
        value={body}
        onChangeText={setBody}
        multiline
        autoCapitalize="none"
        autoCorrect={false}
        placeholder='{"key": "value"}'
        placeholderTextColor="#555"
      />

      {/* Call button */}
      <TouchableOpacity style={styles.callBtn} onPress={call} disabled={loading}>
        {loading ? (
          <ActivityIndicator color="#000" />
        ) : (
          <Text style={styles.callText}>Send Request</Text>
        )}
      </TouchableOpacity>

      {/* Result */}
      {result !== null && (
        <View style={styles.resultBox}>
          {result.status !== undefined && (
            <Text style={styles.statusText}>Status: {result.status}</Text>
          )}
          <Text style={styles.resultText}>
            {JSON.stringify(result.data ?? result.error, null, 2)}
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a', padding: 16 },
  heading: { color: '#fff', fontSize: 22, fontWeight: '700', marginBottom: 16 },
  label: { color: '#aaa', fontSize: 12, marginBottom: 4, marginTop: 12 },
  presetRow: { flexDirection: 'row', marginBottom: 4 },
  presetChip: {
    backgroundColor: '#1e1e1e',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginRight: 8,
  },
  presetText: { color: '#ddd', fontSize: 12 },
  methodRow: { flexDirection: 'row', gap: 8 },
  methodBtn: {
    borderWidth: 1,
    borderColor: '#333',
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  methodBtnActive: { backgroundColor: '#fff', borderColor: '#fff' },
  methodText: { color: '#aaa', fontWeight: '600' },
  methodTextActive: { color: '#000' },
  input: {
    backgroundColor: '#1a1a1a',
    color: '#fff',
    borderRadius: 8,
    padding: 10,
    fontSize: 13,
    fontFamily: 'monospace',
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  bodyInput: { minHeight: 80, textAlignVertical: 'top' },
  callBtn: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
    marginTop: 20,
  },
  callText: { color: '#000', fontWeight: '700', fontSize: 15 },
  resultBox: {
    marginTop: 20,
    backgroundColor: '#111',
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: '#2a2a2a',
    marginBottom: 40,
  },
  statusText: { color: '#4ade80', fontWeight: '700', marginBottom: 6 },
  resultText: { color: '#e2e8f0', fontSize: 12, fontFamily: 'monospace' },
});
