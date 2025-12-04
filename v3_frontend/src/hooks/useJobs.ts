import { useState, useEffect, useCallback } from 'react';
import { jobsService, type JobsFilters } from '../services/jobsService';
import type { JobExecution } from '../types';
import { showToast } from '../utils/toast';

export function useJobs(filters: JobsFilters = {}) {
  const [jobs, setJobs] = useState<JobExecution[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);

  const fetchJobs = useCallback(async (reset: boolean = false) => {
    if (reset) {
      setJobs([]); // Clear immediately so UI shows loading state
    }
    setLoading(true);
    try {
      const currentOffset = reset ? 0 : offset;
      const response = await jobsService.getJobs({
        ...filters,
        offset: currentOffset,
      });

      if (reset) {
        setJobs(response.data || []);
        setOffset(response.pagination?.nextOffset || 0);
      } else {
        setJobs(prev => [...prev, ...(response.data || [])]);
        setOffset(response.pagination?.nextOffset || offset);
      }

      setHasMore(response.pagination?.hasMore || false);
      setTotal(response.pagination?.total || 0);
    } catch (error) {
      showToast.apiError(error);
      if (reset) {
        setJobs([]);
      }
    } finally {
      setLoading(false);
    }
  }, [filters, offset]);

  const loadMore = useCallback(() => {
    if (!loading && hasMore) {
      fetchJobs(false);
    }
  }, [loading, hasMore, fetchJobs]);

  const refetch = useCallback(() => {
    setOffset(0);
    fetchJobs(true);
  }, [fetchJobs]);

  useEffect(() => {
    setOffset(0);
    fetchJobs(true);
  }, [filters]);

  return {
    jobs,
    loading,
    hasMore,
    total,
    loadMore,
    refetch,
  };
}
