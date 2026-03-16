import { apiClient } from './api';
import type { Transcription } from '../types';

export const transcriptionsService = {
  // GET /api/transcription/<transcription_id>
  getTranscriptionById: async (transcriptionId: string): Promise<Transcription> => {
    const response = await apiClient.get<Transcription>(`/api/transcription/${transcriptionId}`);
    return response.data;
  },

  // POST /api/transcription/<transcription_id>/speaker
  updateSpeaker: async (
    transcriptionId: string,
    speakerLabel: string,
    participantId: string,
    manuallyVerified: boolean = true
  ): Promise<void> => {
    await apiClient.post(`/api/transcription/${transcriptionId}/speaker`, {
      speaker_label: speakerLabel,
      participant_id: participantId,
      manually_verified: manuallyVerified,
    });
  },

  // POST /api/transcription/<transcription_id>/speaker/<label>/accept
  acceptSuggestion: async (
    transcriptionId: string,
    speakerLabel: string,
    participantId?: string,
    useForTraining: boolean = false
  ): Promise<void> => {
    const body: Record<string, unknown> = { useForTraining };
    if (participantId) body.participantId = participantId;
    await apiClient.post(
      `/api/transcription/${transcriptionId}/speaker/${encodeURIComponent(speakerLabel)}/accept`,
      body
    );
  },

  // POST /api/transcription/<transcription_id>/speaker/<label>/training
  toggleTraining: async (
    transcriptionId: string,
    speakerLabel: string,
    useForTraining: boolean
  ): Promise<void> => {
    await apiClient.post(
      `/api/transcription/${transcriptionId}/speaker/${encodeURIComponent(speakerLabel)}/training`,
      { useForTraining }
    );
  },

  // POST /api/transcription/<transcription_id>/speaker/<label>/reject
  rejectSuggestion: async (
    transcriptionId: string,
    speakerLabel: string
  ): Promise<void> => {
    await apiClient.post(
      `/api/transcription/${transcriptionId}/speaker/${encodeURIComponent(speakerLabel)}/reject`
    );
  },

  // POST /api/transcription/<transcription_id>/speaker/<label>/dismiss
  dismissSpeaker: async (
    transcriptionId: string,
    speakerLabel: string
  ): Promise<void> => {
    await apiClient.post(
      `/api/transcription/${transcriptionId}/speaker/${encodeURIComponent(speakerLabel)}/dismiss`
    );
  },

  // POST /api/transcription/<transcription_id>/reidentify
  reidentify: async (transcriptionId: string): Promise<void> => {
    await apiClient.post(`/api/transcription/${transcriptionId}/reidentify`);
  },
};
