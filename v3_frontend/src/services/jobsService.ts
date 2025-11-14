import { apiClient } from './api';
import type { JobExecution } from '../types';

export interface JobsFilters {
  limit?: number;
  offset?: number;
  min_duration?: number;
  has_activity?: boolean;
  status?: string; // comma-separated
  trigger_source?: 'scheduled' | 'manual';
  user_id?: string;
  start_date?: string;
  end_date?: string;
  sort_by?: 'startTime' | 'endTime' | 'duration' | 'errors';
  sort_order?: 'asc' | 'desc';
}

export interface JobsListResponse {
  status: string;
  data: JobExecution[];
  pagination: {
    total: number;
    count: number;
    limit: number;
    offset: number;
    hasMore: boolean;
    nextOffset: number;
  };
}

export interface JobDetailsResponse {
  status: string;
  data: JobExecution;
}

export const jobsService = {
  async getJobs(filters: JobsFilters = {}): Promise<JobsListResponse> {
    const params = new URLSearchParams();

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, String(value));
      }
    });

    const response = await apiClient.get(`/api/admin/jobs?${params.toString()}`);
    return response.data;
  },

  async getJobDetails(jobId: string): Promise<JobDetailsResponse> {
    const response = await apiClient.get(`/api/admin/jobs/${jobId}`);
    return response.data;
  },
};
