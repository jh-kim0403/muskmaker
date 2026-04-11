/**
 * TanStack Query hooks.
 *
 * All server state lives here — components never call apiClient directly.
 *
 * Query key conventions:
 *   ['me']                     → current user profile
 *   ['goal-types']             → catalog of goal types
 *   ['goals', 'today']         → today's availability for this user
 *   ['goal', id]               → single goal
 *   ['verification', id]       → single verification (polled for free users)
 *   ['sweepstakes', 'active']  → active sweepstakes list
 *   ['sweepstakes', id]        → single sweepstakes with odds
 *   ['wins']                   → user's winning history
 *   ['notif-prefs']            → notification preferences
 */
import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
} from '@tanstack/react-query';
import * as api from './endpoints';
import type {
  User,
  GoalAvailability,
  Goal,
  Verification,
  SweepstakesWithOdds,
  EnterSweepstakesPayload,
  NotificationPreferences,
  SubmitVerificationPayload,
} from '@/types/api';

// ── User ──────────────────────────────────────────────────────────────────────
export const useMe = (options?: UseQueryOptions<User>) =>
  useQuery({ queryKey: ['me'], queryFn: api.fetchMe, ...options });

export const useUpdateTimezone = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.updateTimezone,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['me'] }),
  });
};

export const useUpdateProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.updateProfile,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['me'] }),
  });
};

// ── Goals ─────────────────────────────────────────────────────────────────────
export const useGoalTypes = () =>
  useQuery({ queryKey: ['goal-types'], queryFn: api.fetchGoalTypes, staleTime: 5 * 60 * 1000 });

export const useTodaysAvailability = () =>
  useQuery({
    queryKey: ['goals', 'today'],
    queryFn: api.fetchTodaysAvailability,
    // Refetch when the app comes to foreground — local day may have changed
    refetchOnWindowFocus: true,
    staleTime: 60 * 1000,
  });

export const useGoal = (goalId: string) =>
  useQuery({
    queryKey: ['goal', goalId],
    queryFn: () => api.fetchGoal(goalId),
    enabled: !!goalId,
  });

export const useCreateGoal = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createGoal,
    onSuccess: () => {
      // Invalidate today's availability so the UI updates immediately
      qc.invalidateQueries({ queryKey: ['goals', 'today'] });
    },
  });
};

// ── Verifications ─────────────────────────────────────────────────────────────
export const useRequestUploadUrl = () =>
  useMutation({ mutationFn: api.requestUploadUrl });

export const useSubmitVerification = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.submitVerification,
    onSuccess: (verification) => {
      // Invalidate goal to reflect 'submitted' status
      qc.invalidateQueries({ queryKey: ['goal', verification.goal_id] });
      qc.invalidateQueries({ queryKey: ['goals', 'today'] });
      // If approved immediately (premium), refresh coin balance
      if (verification.status === 'approved') {
        qc.invalidateQueries({ queryKey: ['me'] });
      }
    },
  });
};

export const useVerificationStatus = (
  verificationId: string | null,
  enabled: boolean
) =>
  useQuery({
    queryKey: ['verification', verificationId],
    queryFn: () => api.fetchVerification(verificationId!),
    enabled: enabled && !!verificationId,
    // Poll every 30 seconds for free users waiting on manual review
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'pending_review' || status === 'in_review') return 30_000;
      return false; // Stop polling once resolved
    },
    // Invalidate user balance when approved
    select: (data) => data,
  });

// ── Sweepstakes ───────────────────────────────────────────────────────────────
export const useActiveSweepstakes = () =>
  useQuery({
    queryKey: ['sweepstakes', 'active'],
    queryFn: api.fetchActiveSweepstakes,
    staleTime: 30 * 1000,
  });

export const useSweepstakes = (id: string) =>
  useQuery({
    queryKey: ['sweepstakes', id],
    queryFn: () => api.fetchSweepstakes(id),
    enabled: !!id,
    // Refetch frequently to keep odds display fresh
    refetchInterval: 15_000,
  });

export const useEnterSweepstakes = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.enterSweepstakes,
    onSuccess: (data, variables) => {
      // Update coin balance optimistically via cache invalidation
      qc.invalidateQueries({ queryKey: ['me'] });
      qc.invalidateQueries({ queryKey: ['sweepstakes', variables.sweepstakes_id] });
      qc.invalidateQueries({ queryKey: ['sweepstakes', 'active'] });
    },
  });
};

export const useMyWins = () =>
  useQuery({ queryKey: ['wins'], queryFn: api.fetchMyWins });

// ── Notifications ─────────────────────────────────────────────────────────────
export const useNotificationPreferences = () =>
  useQuery({ queryKey: ['notif-prefs'], queryFn: api.fetchNotificationPreferences });

export const useUpdateNotificationPreferences = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.updateNotificationPreferences,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notif-prefs'] }),
  });
};
