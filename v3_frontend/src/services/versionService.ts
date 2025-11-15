import { apiClient } from './api';

interface VersionResponse {
  version: string;
}

export const versionService = {
  async getVersion(): Promise<string> {
    try {
      const response = await apiClient.get<VersionResponse>('/api/get_api_version');
      return response.data.version;
    } catch (error) {
      console.error('Failed to fetch API version:', error);
      return 'unknown';
    }
  }
};
