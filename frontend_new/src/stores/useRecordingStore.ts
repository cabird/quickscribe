import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { Recording } from '../types';

interface RecordingState {
  recordings: Recording[];
  loading: boolean;
  error: string | null;
  
  // Actions
  setRecordings: (recordings: Recording[]) => void;
  addRecording: (recording: Recording) => void;
  updateRecording: (recording: Recording) => void;
  removeRecording: (recordingId: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  
  // Derived data
  getRecordingById: (id: string) => Recording | undefined;
  getRecordingsByTag: (tagId: string) => Recording[];
  getRecordingsByStatus: (status: Recording['transcription_status']) => Recording[];
}

export const useRecordingStore = create<RecordingState>()(
  devtools(
    (set, get) => ({
      recordings: [],
      loading: false,
      error: null,

      setRecordings: (recordings) =>
        set({ recordings }, false, 'setRecordings'),

      addRecording: (recording) =>
        set(
          (state) => ({
            recordings: [recording, ...state.recordings],
          }),
          false,
          'addRecording'
        ),

      updateRecording: (updatedRecording) =>
        set(
          (state) => ({
            recordings: state.recordings.map((recording) =>
              recording.id === updatedRecording.id ? updatedRecording : recording
            ),
          }),
          false,
          'updateRecording'
        ),

      removeRecording: (recordingId) =>
        set(
          (state) => ({
            recordings: state.recordings.filter((recording) => recording.id !== recordingId),
          }),
          false,
          'removeRecording'
        ),

      setLoading: (loading) =>
        set({ loading }, false, 'setLoading'),

      setError: (error) =>
        set({ error }, false, 'setError'),

      // Derived data
      getRecordingById: (id) => {
        const state = get();
        return state.recordings.find((recording) => recording.id === id);
      },

      getRecordingsByTag: (tagId) => {
        const state = get();
        return state.recordings.filter(
          (recording) => recording.tagIds?.includes(tagId)
        );
      },

      getRecordingsByStatus: (status) => {
        const state = get();
        return state.recordings.filter(
          (recording) => recording.transcription_status === status
        );
      },
    }),
    {
      name: 'recording-store',
    }
  )
);