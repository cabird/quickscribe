import { useState, useEffect, useCallback } from 'react';
import { participantsService } from '../services/participantsService';
import type { Participant } from '../types';

interface UseParticipantsResult {
  participants: Participant[];
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useParticipants(): UseParticipantsResult {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchParticipants = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await participantsService.getParticipants();
      setParticipants(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchParticipants();
  }, [fetchParticipants]);

  return {
    participants,
    loading,
    error,
    refetch: fetchParticipants,
  };
}
