import { apiClient } from './api';
import type { Recording, Transcription, TopCandidate } from '../types';

export interface ReviewItem {
  recording: Recording;
  transcription: Transcription;
  suggestCount: number;
  unknownCount: number;
}

export interface ReviewListResponse {
  status: string;
  data: ReviewItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditEntry {
  recordingId: string;
  recordingTitle: string;
  transcriptionId: string;
  speakerLabel: string;
  currentDisplayName?: string;
  currentParticipantId?: string;
  currentStatus?: string;
  timestamp: string;
  action: string;
  source?: string;
  participantId?: string;
  displayName?: string;
  similarity?: number;
  candidatesPresented?: TopCandidate[];
}

export interface AuditListResponse {
  status: string;
  data: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

export const speakerReviewService = {
  // GET /api/speaker-reviews
  getReviews: async (
    status: 'all' | 'suggest' | 'unknown' = 'all',
    limit: number = 50,
    offset: number = 0
  ): Promise<ReviewListResponse> => {
    const response = await apiClient.get<ReviewListResponse>('/api/speaker-reviews', {
      params: { status, limit, offset },
    });
    return response.data;
  },

  // GET /api/speaker-audit
  getAuditLog: async (
    limit: number = 100,
    offset: number = 0
  ): Promise<AuditListResponse> => {
    const response = await apiClient.get<AuditListResponse>('/api/speaker-audit', {
      params: { limit, offset },
    });
    return response.data;
  },

  // POST /api/transcription/<id>/speaker/<label>/reassign
  reassignSpeaker: async (
    transcriptionId: string,
    speakerLabel: string,
    participantId: string,
    useForTraining: boolean = false
  ): Promise<void> => {
    await apiClient.post(
      `/api/transcription/${transcriptionId}/speaker/${encodeURIComponent(speakerLabel)}/reassign`,
      { participantId, useForTraining }
    );
  },

  // POST /api/speaker-profiles/rebuild
  rebuildProfiles: async (): Promise<{ success: boolean; message: string; stats: Record<string, number> }> => {
    const response = await apiClient.post('/api/speaker-profiles/rebuild');
    return response.data;
  },
};
