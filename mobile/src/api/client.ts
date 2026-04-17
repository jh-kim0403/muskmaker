/**
 * Axios API client.
 *
 * - Attaches Firebase ID token as Authorization: Bearer <token> on every request
 * - Refreshes the token automatically when it expires (Firebase handles this)
 * - Centralizes base URL configuration
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { getAuth, getIdToken } from '@react-native-firebase/auth';

const firebaseAuth = getAuth();
import Constants from 'expo-constants';

const appEnv = Constants.expoConfig?.extra?.appEnv ?? 'development';
const configuredApiUrl = Constants.expoConfig?.extra?.apiUrl;
const BASE_URL =
  configuredApiUrl ??
  (appEnv === 'development' ? 'http://192.168.1.151:8000/api/v1' : undefined);

if (!BASE_URL) {
  throw new Error(`Missing API_URL for APP_ENV=${appEnv}`);
}

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Request interceptor: attach Firebase JWT ──────────────────────────────────
apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const currentUser = firebaseAuth.currentUser;
  if (currentUser) {
    // forceRefresh=false — Firebase caches and auto-refreshes the token
    const token = await getIdToken(currentUser, false);
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Response interceptor: normalize errors ────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail: string }>) => {
    const detail = error.response?.data?.detail ?? 'An unexpected error occurred';
    const status = error.response?.status ?? 0;
    return Promise.reject({ detail, status, original: error });
  }
);
