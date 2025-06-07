import axios from 'axios';
import type { 
  PlaudSettings, 
  PlaudSyncResponse, 
  PlaudSyncStatusResponse, 
  PlaudSettingsResponse,
  SyncProgress,
  ActiveSyncCheckResponse
} from '../types/index';

export const startPlaudSync = async (dryRun: boolean = false): Promise<PlaudSyncResponse> => {
  const response = await axios.post('/plaud/sync/start', { dry_run: dryRun });
  return response.data;
};

export const getPlaudSettings = async (): Promise<PlaudSettingsResponse> => {
  const response = await axios.get('/plaud/user/plaud_settings');
  return response.data;
};

export const updatePlaudSettings = async (settings: Partial<PlaudSettings>): Promise<PlaudSettingsResponse> => {
  const response = await axios.put('/plaud/user/plaud_settings', { plaudSettings: settings });
  return response.data;
};

export const getPlaudSyncStatus = async (userId: string): Promise<PlaudSyncStatusResponse> => {
  const response = await axios.get(`/plaud/plaud_sync/status/${userId}`);
  return response.data;
};

export const getSyncProgress = async (syncToken: string): Promise<SyncProgress> => {
  const response = await axios.get(`/plaud/sync/progress/${syncToken}`);
  return response.data;
};

export const checkActiveSync = async (): Promise<ActiveSyncCheckResponse> => {
  const response = await axios.get('/plaud/sync/check_active');
  return response.data;
};