import { useState, useEffect, useCallback } from 'react';
import { participantsService } from '../services/participantsService';
import type { Participant, Recording } from '../types';

interface UseParticipantDetailsResult {
  participant: Participant | null;
  recordings: Recording[];
  totalRecordings: number;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useParticipantDetails(
  participantId: string | null
): UseParticipantDetailsResult {
  const [participant, setParticipant] = useState<Participant | null>(null);
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [totalRecordings, setTotalRecordings] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchDetails = useCallback(async () => {
    if (!participantId) {
      setParticipant(null);
      setRecordings([]);
      setTotalRecordings(0);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Fetch participant details and recordings in parallel
      const [participantData, recordingsData] = await Promise.all([
        participantsService.getParticipantById(participantId),
        participantsService.getParticipantRecordings(participantId, 5, 0),
      ]);

      setParticipant(participantData);
      setRecordings(recordingsData.recordings);
      setTotalRecordings(recordingsData.total);
    } catch (err) {
      setError(err as Error);
      setParticipant(null);
      setRecordings([]);
      setTotalRecordings(0);
    } finally {
      setLoading(false);
    }
  }, [participantId]);

  useEffect(() => {
    fetchDetails();
  }, [fetchDetails]);

  return {
    participant,
    recordings,
    totalRecordings,
    loading,
    error,
    refetch: fetchDetails,
  };
}
