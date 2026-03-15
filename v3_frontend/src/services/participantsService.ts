import { apiClient } from './api';
import type {
  Participant,
  Recording,
  CreateParticipantRequest,
  CreateParticipantResponse,
  UpdateParticipantRequest,
  UpdateParticipantResponse,
  GetParticipantsResponse,
  GetParticipantResponse,
  GetParticipantRecordingsResponse,
  DeleteParticipantResponse,
  MergeParticipantsRequest,
  MergeParticipantsResponse,
} from '../types';

export const participantsService = {
  // GET /api/participants - Get all participants for current user
  getParticipants: async (): Promise<Participant[]> => {
    const response = await apiClient.get<GetParticipantsResponse>('/api/participants');
    return response.data.data || [];
  },

  // POST /api/participants - Create a new participant
  createParticipant: async (data: CreateParticipantRequest): Promise<Participant> => {
    const response = await apiClient.post<CreateParticipantResponse>('/api/participants', data);
    if (!response.data.data) {
      throw new Error('Failed to create participant');
    }
    return response.data.data;
  },

  // GET /api/participants/search?name=...&fuzzy=true - Search participants by name
  searchParticipants: async (name: string, fuzzy: boolean = true): Promise<Participant[]> => {
    const response = await apiClient.get<GetParticipantsResponse>(
      `/api/participants/search?name=${encodeURIComponent(name)}&fuzzy=${fuzzy}`
    );
    return response.data.data || [];
  },

  // GET /api/participants/:id - Get a specific participant by ID
  getParticipantById: async (participantId: string): Promise<Participant | null> => {
    const response = await apiClient.get<GetParticipantResponse>(
      `/api/participants/${encodeURIComponent(participantId)}`
    );
    return response.data.data || null;
  },

  // GET /api/participants/:id/recordings - Get recordings where participant appears
  getParticipantRecordings: async (
    participantId: string,
    limit: number = 5,
    offset: number = 0
  ): Promise<{ recordings: Recording[]; total: number }> => {
    const response = await apiClient.get<GetParticipantRecordingsResponse>(
      `/api/participants/${encodeURIComponent(participantId)}/recordings?limit=${limit}&offset=${offset}`
    );
    return {
      recordings: response.data.data || [],
      total: response.data.total || 0,
    };
  },

  // PUT /api/participants/:id - Update an existing participant
  updateParticipant: async (
    participantId: string,
    data: UpdateParticipantRequest
  ): Promise<Participant> => {
    const response = await apiClient.put<UpdateParticipantResponse>(
      `/api/participants/${encodeURIComponent(participantId)}`,
      data
    );
    if (!response.data.data) {
      throw new Error('Failed to update participant');
    }
    return response.data.data;
  },

  // DELETE /api/participants/:id - Delete a participant
  deleteParticipant: async (participantId: string): Promise<void> => {
    await apiClient.delete<DeleteParticipantResponse>(
      `/api/participants/${encodeURIComponent(participantId)}`
    );
  },

  // POST /api/participants/:id/merge/:otherId - Merge two participants
  // The first participant (primaryId) will be kept, second (secondaryId) will be deleted
  mergeParticipants: async (
    primaryId: string,
    secondaryId: string,
    mergeFields?: MergeParticipantsRequest['merge_fields']
  ): Promise<Participant> => {
    const response = await apiClient.post<MergeParticipantsResponse>(
      `/api/participants/${encodeURIComponent(primaryId)}/merge/${encodeURIComponent(secondaryId)}`,
      { merge_fields: mergeFields }
    );
    if (!response.data.data) {
      throw new Error('Failed to merge participants');
    }
    return response.data.data;
  },

  // Helper: Find or create a participant by name
  // If a participant with matching name exists, return it
  // Otherwise, create a new participant and return it
  findOrCreateParticipant: async (inputName: string): Promise<Participant> => {
    const trimmedName = inputName.trim();
    const spaceIndex = trimmedName.indexOf(' ');

    // Parse the input name
    let firstName: string;
    let lastName: string | undefined;

    if (spaceIndex > 0) {
      firstName = trimmedName.substring(0, spaceIndex);
      lastName = trimmedName.substring(spaceIndex + 1);
    } else {
      firstName = trimmedName;
      lastName = undefined;
    }

    // Search for existing participant
    const existing = await participantsService.searchParticipants(trimmedName, true);

    // Check for match by full name (firstName + lastName) or displayName
    const match = existing.find(p => {
      // Check if firstName + lastName matches
      if (p.firstName && p.lastName) {
        const fullName = `${p.firstName} ${p.lastName}`.toLowerCase();
        if (fullName === trimmedName.toLowerCase()) {
          return true;
        }
      }
      // Check displayName match
      if (p.displayName.toLowerCase() === trimmedName.toLowerCase()) {
        return true;
      }
      // For single name input, match on firstName or displayName
      if (!lastName) {
        if (p.firstName?.toLowerCase() === firstName.toLowerCase()) {
          return true;
        }
        if (p.displayName.toLowerCase() === firstName.toLowerCase()) {
          return true;
        }
      }
      return false;
    });

    if (match) {
      return match;
    }

    // No match found, create new participant
    // displayName = the full name as entered (for consistent matching)
    // firstName/lastName stored separately (for structured data)
    if (lastName) {
      return participantsService.createParticipant({
        displayName: trimmedName,  // Full name for consistent matching
        firstName,
        lastName,
      });
    }

    // Single name - use as displayName and firstName
    return participantsService.createParticipant({
      displayName: trimmedName,
      firstName,
    });
  },
};
