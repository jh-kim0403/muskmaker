/**
 * All API call functions.
 * These are plain async functions — TanStack Query hooks wrap them with caching.
 * Never call apiClient directly outside this file.
 */
import { apiClient } from './client';
import type {
  User,
  GoalType,
  GoalAvailability,
  Goal,
  UploadUrlResponse,
  SubmitVerificationPayload,
  Verification,
  SweepstakesWithOdds,
  EnterSweepstakesPayload,
  EnterSweepstakesResponse,
  Winner,
  NotificationPreferences,
} from '@/types/api';

// ── Users ─────────────────────────────────────────────────────────────────────
export const fetchMe = (): Promise<User> =>
  apiClient.get('/users/me').then((r) => r.data);

export const updateTimezone = (timezone: string): Promise<User> =>
  apiClient.patch('/users/me/timezone', { timezone }).then((r) => r.data);

export const updateProfile = (data: { display_name?: string }): Promise<User> =>
  apiClient.patch('/users/me', data).then((r) => r.data);

export const registerPushToken = (expo_push_token: string, platform: 'ios' | 'android') =>
  apiClient.post('/users/me/push-token', { expo_push_token, platform });

export const fetchNotificationPreferences = (): Promise<NotificationPreferences> =>
  apiClient.get('/users/me/notification-preferences').then((r) => r.data);

export const updateNotificationPreferences = (
  data: Partial<NotificationPreferences>
): Promise<NotificationPreferences> =>
  apiClient.patch('/users/me/notification-preferences', data).then((r) => r.data);

// ── Goals ─────────────────────────────────────────────────────────────────────
export const fetchGoalTypes = (): Promise<GoalType[]> =>
  apiClient.get('/goals/types').then((r) => r.data);

export const fetchTodaysAvailability = (): Promise<GoalAvailability[]> =>
  apiClient.get('/goals/today').then((r) => r.data);

export const createGoal = (data: { goal_type_id: string; notes?: string }): Promise<Goal> =>
  apiClient.post('/goals/', data).then((r) => r.data);

export const fetchGoal = (goalId: string): Promise<Goal> =>
  apiClient.get(`/goals/${goalId}`).then((r) => r.data);

// ── Verifications ─────────────────────────────────────────────────────────────
export const requestUploadUrl = (data: {
  goal_id: string;
  photo_index: number;
  mime_type?: string;
}): Promise<UploadUrlResponse> =>
  apiClient.post('/verifications/upload-url', data).then((r) => r.data);

export const submitVerification = (data: SubmitVerificationPayload): Promise<Verification> =>
  apiClient.post('/verifications/submit', data).then((r) => r.data);

export const fetchVerification = (verificationId: string): Promise<Verification> =>
  apiClient.get(`/verifications/${verificationId}`).then((r) => r.data);

/**
 * Upload a photo directly to S3 using the pre-signed PUT URL.
 * This never goes through the backend — pure S3 upload.
 */
export const uploadPhotoToS3 = async (
  uploadUrl: string,
  photoUri: string,
  mimeType: string = 'image/jpeg'
): Promise<void> => {
  const blob = await uriToBlob(photoUri);
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    body: blob,
    headers: { 'Content-Type': mimeType },
  });
  if (!response.ok) {
    throw new Error(`S3 upload failed: ${response.status} ${response.statusText}`);
  }
};

const uriToBlob = (uri: string): Promise<Blob> =>
  new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.onload = () => resolve(xhr.response);
    xhr.onerror = () => reject(new Error('Failed to convert URI to Blob'));
    xhr.responseType = 'blob';
    xhr.open('GET', uri, true);
    xhr.send(null);
  });

// ── Sweepstakes ───────────────────────────────────────────────────────────────
export const fetchActiveSweepstakes = (): Promise<SweepstakesWithOdds[]> =>
  apiClient.get('/sweepstakes/active').then((r) => r.data);

export const fetchSweepstakes = (id: string): Promise<SweepstakesWithOdds> =>
  apiClient.get(`/sweepstakes/${id}`).then((r) => r.data);

export const enterSweepstakes = (data: EnterSweepstakesPayload): Promise<EnterSweepstakesResponse> =>
  apiClient.post('/sweepstakes/enter', data).then((r) => r.data);

export const fetchMyWins = (): Promise<Winner[]> =>
  apiClient.get('/sweepstakes/my/wins').then((r) => r.data);
