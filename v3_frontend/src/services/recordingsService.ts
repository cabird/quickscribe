import { apiClient } from './api';
import type { Recording } from '../types';

export const recordingsService = {
  // GET /api/recordings
  getAllRecordings: async (): Promise<Recording[]> => {
    const response = await apiClient.get<Recording[]>('/api/recordings');
    return response.data;
  },

  // GET /api/recording/<recording_id>
  getRecordingById: async (recordingId: string): Promise<Recording> => {
    const response = await apiClient.get<Recording>(`/api/recording/${recordingId}`);
    return response.data;
  },

  // GET /api/recording/<recording_id>/audio-url
  getRecordingAudioUrl: async (recordingId: string): Promise<{ audio_url: string; expires_in: number }> => {
    const response = await apiClient.get(`/api/recording/${recordingId}/audio-url`);
    return response.data;
  },

  // PUT /api/recording/<recording_id>
  updateRecording: async (recordingId: string, updates: Partial<Recording>): Promise<Recording> => {
    const response = await apiClient.put(`/api/recording/${recordingId}`, updates);
    return response.data;
  },

  // DELETE /api/delete_recording/<recording_id>
  deleteRecording: async (recordingId: string): Promise<void> => {
    await apiClient.get(`/api/delete_recording/${recordingId}`);
  },
};
