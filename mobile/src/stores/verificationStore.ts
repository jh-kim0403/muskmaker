/**
 * Verification flow store.
 *
 * Tracks the multi-step camera → preview → submit flow.
 * This state is ephemeral (not persisted) — if the user backgrounds the app
 * mid-flow, they start over (intentional anti-cheat: photos must be fresh).
 */
import { create } from 'zustand';
import type { VerificationPath } from '@/types/api';

export interface CapturedPhoto {
  uri: string;         // local file URI from Vision Camera
  s3Key: string | null; // set after upload to S3
  photoIndex: number;  // 0 or 1
}

export interface LocationData {
  lat: number;
  lng: number;
  accuracyMeters: number;
  capturedAt: string; // ISO string
}

interface VerificationFlowState {
  // The goal being verified
  goalId: string | null;
  verificationPath: VerificationPath | null;

  // Photos captured in this session
  photos: CapturedPhoto[];

  // Location data (premium_ai_location path only)
  location: LocationData | null;

  // Upload progress
  isUploading: boolean;
  uploadError: string | null;

  // Actions
  startFlow: (goalId: string, path: VerificationPath) => void;
  addPhoto: (photo: CapturedPhoto) => void;
  setPhotoS3Key: (photoIndex: number, s3Key: string) => void;
  setLocation: (location: LocationData | null) => void;
  setUploading: (isUploading: boolean) => void;
  setUploadError: (error: string | null) => void;
  resetFlow: () => void;

  // Computed
  requiredPhotoCount: () => number;
  isReadyToSubmit: () => boolean;
}

const PHOTO_COUNTS: Record<VerificationPath, number> = {
  free_manual: 2,
  premium_ai_standard: 2,
  premium_ai_location: 1,
};

const initialState = {
  goalId: null,
  verificationPath: null,
  photos: [],
  location: null,
  isUploading: false,
  uploadError: null,
};

export const useVerificationStore = create<VerificationFlowState>((set, get) => ({
  ...initialState,

  startFlow: (goalId, path) =>
    set({ ...initialState, goalId, verificationPath: path }),

  addPhoto: (photo) =>
    set((state) => ({ photos: [...state.photos, photo] })),

  setPhotoS3Key: (photoIndex, s3Key) =>
    set((state) => ({
      photos: state.photos.map((p) =>
        p.photoIndex === photoIndex ? { ...p, s3Key } : p
      ),
    })),

  setLocation: (location) => set({ location }),

  setUploading: (isUploading) => set({ isUploading }),

  setUploadError: (error) => set({ uploadError: error }),

  resetFlow: () => set(initialState),

  requiredPhotoCount: () => {
    const path = get().verificationPath;
    return path ? PHOTO_COUNTS[path] : 2;
  },

  isReadyToSubmit: () => {
    const { photos, verificationPath, location } = get();
    const required = get().requiredPhotoCount();
    const allPhotosUploaded = photos.length === required && photos.every((p) => p.s3Key !== null);

    if (verificationPath === 'premium_ai_location') {
      return allPhotosUploaded && location !== null;
    }
    return allPhotosUploaded;
  },
}));
