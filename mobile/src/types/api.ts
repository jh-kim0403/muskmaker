// ── Shared API response types ─────────────────────────────────────────────────
// Mirror the Pydantic response schemas from the backend.

export interface User {
  id: string;
  firebase_uid: string;
  email: string | null;
  display_name: string | null;
  timezone: string;
  subscription_tier: 'free' | 'premium';
  subscription_expires_at: string | null;
  coin_balance: number;
  is_premium: boolean;
  has_completed_onboarding: boolean;
  created_at: string;
}

export interface GoalType {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  icon_url: string | null;
  coin_reward: number;
  difficulty: 'easy' | 'medium' | 'hard';
  supports_location_path: boolean;
}

export interface Goal {
  id: string;
  goal_type_id: string;
  goal_type: GoalType;
  title: string;
  status: 'active' | 'submitted' | 'approved' | 'rejected' | 'expired';
  notes: string | null;
  local_goal_date: string;
  timezone_at_creation: string;
  expires_at: string;
  created_at: string;
}

export interface UploadUrlResponse {
  upload_url: string;
  s3_key: string;
  expires_at: string;
}

export type VerificationPath = 'free_manual' | 'premium_ai_standard' | 'premium_ai_location';

export interface SubmitVerificationPayload {
  goal_id: string;
  verification_path: VerificationPath;
  photo_s3_keys: string[];
  location_lat?: number;
  location_lng?: number;
  location_accuracy_meters?: number;
  location_captured_at?: string;
}

export interface VerificationPhoto {
  id: string;
  photo_index: number;
  photo_url: string;
  exif_captured_at: string | null;
  created_at: string;
}

export interface Verification {
  id: string;
  goal_id: string;
  status: 'pending_review' | 'in_review' | 'approved' | 'rejected';
  verification_path: VerificationPath;
  submitted_at: string;
  coins_awarded: number;
  coins_awarded_at: string | null;
  photos: VerificationPhoto[];
  rejection_reason: string | null;
  reviewed_at: string | null;
}

export interface SweepstakesWithOdds {
  id: string;
  title: string;
  description: string | null;
  prize_description: string;
  status: string;
  starts_at: string;
  ends_at: string;
  draw_at: string | null;
  total_entries_count: number;
  winner_count: number;
  no_purchase_necessary: boolean;
  sponsor_name: string;
  apple_not_sponsor: boolean;
  user_entries: number;
  estimated_odds: number | null;
}

export interface EnterSweepstakesPayload {
  sweepstakes_id: string;
  coins_to_spend: number;
}

export interface EnterSweepstakesResponse {
  entry_id: string;
  coins_entered: number;
  new_coin_balance: number;
  user_total_entries: number;
  total_pool_entries: number;
  estimated_odds: number;
}

export interface Winner {
  id: string;
  sweepstakes_id: string;
  prize_description: string;
  claim_status: 'pending' | 'notified' | 'claimed' | 'expired' | 'forfeited';
  notified_at: string | null;
  claim_deadline: string | null;
}

export interface NotificationPreferences {
  id: string;
  push_enabled: boolean;
  email_enabled: boolean;
  goal_reminder_enabled: boolean;
  reminder_minutes_before_expiry: number;
  notification_tone: 'normal' | 'friendly_banter' | 'harsh';
  sweep_result_enabled: boolean;
  new_sweep_enabled: boolean;
}
