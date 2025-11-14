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
};
