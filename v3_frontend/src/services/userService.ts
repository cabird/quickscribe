import { apiClient } from './api';
import type { User, PlaudSettings } from '../types';

export interface UpdatePlaudSettingsRequest {
  enableSync?: boolean;
  bearerToken?: string;
}

export interface UpdatePlaudSettingsResponse {
  status: string;
  message: string;
  plaudSettings: PlaudSettings | null;
}

export const userService = {
  /**
   * Get the current authenticated user's profile.
   */
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get('/api/me');
    return response.data;
  },

  /**
   * Update the current user's Plaud integration settings.
   */
  async updatePlaudSettings(
    userId: string,
    settings: UpdatePlaudSettingsRequest
  ): Promise<UpdatePlaudSettingsResponse> {
    const response = await apiClient.put('/api/me/plaud-settings', settings);
    return response.data;
  },
};
