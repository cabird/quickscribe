import { useState, useEffect } from 'react';
import { transcriptionsService } from '../services/transcriptionsService';
import type { Transcription } from '../types';

interface UseTranscriptionResult {
  transcription: Transcription | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useTranscription(transcriptionId: string | null): UseTranscriptionResult {
  const [transcription, setTranscription] = useState<Transcription | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchTranscription = async () => {
    if (!transcriptionId) {
      setTranscription(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await transcriptionsService.getTranscriptionById(transcriptionId);
      setTranscription(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTranscription();
  }, [transcriptionId]);

  // Listen for transcriptionUpdated events (e.g. after speaker assignment)
  useEffect(() => {
    const handleUpdate = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (detail?.transcriptionId === transcriptionId) {
        fetchTranscription();
      }
    };
    window.addEventListener('transcriptionUpdated', handleUpdate);
    return () => window.removeEventListener('transcriptionUpdated', handleUpdate);
  }, [transcriptionId]);

  return {
    transcription,
    loading,
    error,
    refetch: fetchTranscription,
  };
}
