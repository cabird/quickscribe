import { useState, useEffect } from 'react';
import { recordingsService } from '../services/recordingsService';
import type { Recording } from '../types';

interface UseRecordingsResult {
  recordings: Recording[];
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useRecordings(): UseRecordingsResult {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchRecordings = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await recordingsService.getAllRecordings();
      setRecordings(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecordings();
  }, []);

  return {
    recordings,
    loading,
    error,
    refetch: fetchRecordings,
  };
}
