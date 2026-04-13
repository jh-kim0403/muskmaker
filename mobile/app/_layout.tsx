/**
 * Root layout — runs on every screen.
 *
 * Responsibilities:
 *  1. Initialize Firebase Auth listener → populate Zustand auth store
 *  2. Initialize RevenueCat → subscription entitlement check
 *  3. Register Expo Push token
 *  4. Detect and sync device timezone to backend (once per app session)
 *  5. Route unauthenticated users to (auth) group
 *  6. Provide TanStack Query client to the entire tree
 */
import { useEffect } from 'react';
import { Stack } from 'expo-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getAuth, onAuthStateChanged } from '@react-native-firebase/auth';

const firebaseAuth = getAuth();
import Purchases from 'react-native-purchases';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { useAuthStore } from '@/stores/authStore';
import { fetchMe, registerPushToken, updateTimezone } from '@/api/endpoints';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30_000,
    },
  },
});

// Configure how push notifications are handled while the app is foregrounded
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export default function RootLayout() {
  const { setFirebaseUid, setUser, clearAuth } = useAuthStore();

  // ── Firebase Auth listener ─────────────────────────────────────────────────
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(firebaseAuth, async (firebaseUser) => {
      if (firebaseUser) {
        setFirebaseUid(firebaseUser.uid);
        try {
          // Fetch/provision user row on backend
          const user = await fetchMe();
          setUser(user);

          // Sync RevenueCat to this Firebase user
          await Purchases.logIn(firebaseUser.uid);

          // Sync device timezone (once per session — backend rate-limits changes)
          const deviceTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
          if (deviceTz && deviceTz !== user.timezone) {
            try {
              const updated = await updateTimezone(deviceTz);
              setUser(updated);
            } catch {
              // Rate limited or invalid tz — not critical, continue
            }
          }

          // Register push token
          await registerExpoPushToken(firebaseUser.uid);
        } catch (err) {
          console.error('Post-auth setup failed:', err);
        }
      } else {
        clearAuth();
        await Purchases.logOut().catch(() => {});
      }
    });

    return () => unsubscribe();
  }, []);

  // ── RevenueCat initialization ──────────────────────────────────────────────
  useEffect(() => {
    const rcKey = Platform.select({
      ios: Constants.expoConfig?.extra?.revenueCatKeyIos,
      android: Constants.expoConfig?.extra?.revenueCatKeyAndroid,
    });
    if (rcKey) {
      Purchases.configure({ apiKey: rcKey });
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="goals/create" options={{ presentation: 'modal' }} />
        <Stack.Screen name="verification/camera" options={{ presentation: 'fullScreenModal' }} />
        <Stack.Screen name="verification/preview" options={{ presentation: 'modal' }} />
        <Stack.Screen name="verification/status" />
        <Stack.Screen name="paywall" options={{ presentation: 'modal' }} />
      </Stack>
    </QueryClientProvider>
  );
}

async function registerExpoPushToken(firebaseUid: string) {
  try {
    const { status } = await Notifications.requestPermissionsAsync();
    if (status !== 'granted') return;

    const tokenData = await Notifications.getExpoPushTokenAsync({
      projectId: Constants.expoConfig?.extra?.eas?.projectId,
    });

    const platform = Platform.OS as 'ios' | 'android';
    await registerPushToken(tokenData.data, platform);
  } catch (err) {
    console.warn('Push token registration failed:', err);
  }
}
