/**
 * Auth store — Firebase session and user profile.
 *
 * Zustand is used for auth state because:
 *   1. It must be available synchronously (no loading state for "am I logged in?")
 *   2. It's needed in the root layout before TanStack Query is hydrated
 *   3. The subscription tier check (is_premium) must be cheap and synchronous
 */
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { MMKV } from 'react-native-mmkv';
import type { User } from '@/types/api';

// MMKV is faster than AsyncStorage and synchronous — used as Zustand persist storage
const storage = new MMKV({ id: 'auth-store' });

const mmkvStorage = {
  getItem: (key: string) => storage.getString(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
};

interface AuthState {
  // Firebase auth state
  firebaseUid: string | null;
  isAuthenticated: boolean;

  // Cached user profile (refreshed from server)
  user: User | null;

  // Actions
  setFirebaseUid: (uid: string | null) => void;
  setUser: (user: User | null) => void;
  clearAuth: () => void;

  // Computed (derived from cached user)
  isPremium: () => boolean;
  coinBalance: () => number;
  timezone: () => string;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      firebaseUid: null,
      isAuthenticated: false,
      user: null,

      setFirebaseUid: (uid) =>
        set({ firebaseUid: uid, isAuthenticated: uid !== null }),

      setUser: (user) => set({ user }),

      clearAuth: () =>
        set({ firebaseUid: null, isAuthenticated: false, user: null }),

      // Computed helpers — used throughout the app
      isPremium: () => {
        const user = get().user;
        if (!user || user.subscription_tier !== 'premium') return false;
        if (!user.subscription_expires_at) return false;
        return new Date(user.subscription_expires_at) > new Date();
      },

      coinBalance: () => get().user?.coin_balance ?? 0,

      timezone: () => get().user?.timezone ?? 'UTC',
    }),
    {
      name: 'auth-store',
      storage: createJSONStorage(() => mmkvStorage),
      // Only persist the user profile — Firebase session is managed by Firebase SDK
      partialize: (state) => ({ user: state.user, firebaseUid: state.firebaseUid }),
    }
  )
);
