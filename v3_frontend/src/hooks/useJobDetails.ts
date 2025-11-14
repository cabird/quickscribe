import { useState, useEffect } from 'react';
import { jobsService } from '../services/jobsService';
import type { JobExecution } from '../types';
import { showToast } from '../utils/toast';

export function useJobDetails(jobId: string | null) {
  const [jobDetails, setJobDetails] = useState<JobExecution | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!jobId) {
      setJobDetails(null);
      return;
    }

    const fetchJobDetails = async () => {
      setLoading(true);
      try {
        const response = await jobsService.getJobDetails(jobId);
        setJobDetails(response.data);
      } catch (error) {
        showToast.apiError(error);
        setJobDetails(null);
      } finally {
        setLoading(false);
      }
    };

    fetchJobDetails();
  }, [jobId]);

  return { jobDetails, loading };
}
