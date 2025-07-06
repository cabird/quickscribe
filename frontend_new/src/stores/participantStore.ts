import { create } from 'zustand';
import axios from 'axios';

interface Participant {
  id: string;
  displayName: string;
  firstName?: string;
  lastName?: string;
  email?: string;
  role?: string;
  organization?: string;
  aliases: string[];
  notes?: string;
  relationshipToUser?: string;
  createdAt: string;
  updatedAt: string;
  firstSeen: string;
  lastSeen: string;
  userId: string;
  partitionKey: string;
  isUser?: boolean;
}

interface ParticipantStore {
  participants: Participant[];
  loading: boolean;
  error: string | null;
  fetchParticipants: () => Promise<void>;
  searchParticipants: (searchTerm: string) => Promise<Participant[]>;
  createParticipant: (data: Partial<Participant>) => Promise<Participant>;
  updateParticipant: (id: string, data: Partial<Participant>) => Promise<Participant>;
  deleteParticipant: (id: string) => Promise<void>;
}

export const useParticipantStore = create<ParticipantStore>((set, get) => ({
  participants: [],
  loading: false,
  error: null,

  fetchParticipants: async () => {
    set({ loading: true, error: null });
    try {
      const response = await axios.get('/api/participants');
      set({ participants: response.data.data || [], loading: false });
    } catch (error: any) {
      set({ 
        error: error.response?.data?.error || 'Failed to fetch participants', 
        loading: false 
      });
    }
  },

  searchParticipants: async (searchTerm: string) => {
    try {
      const response = await axios.get(`/api/participants/search?search=${encodeURIComponent(searchTerm)}`);
      return response.data.data || [];
    } catch (error: any) {
      console.error('Failed to search participants:', error);
      return [];
    }
  },

  createParticipant: async (data: Partial<Participant>) => {
    try {
      const response = await axios.post('/api/participants', data);
      const newParticipant = response.data.data;
      
      // Add to local state
      set(state => ({
        participants: [...state.participants, newParticipant]
      }));
      
      return newParticipant;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || 'Failed to create participant');
    }
  },

  updateParticipant: async (id: string, data: Partial<Participant>) => {
    try {
      const response = await axios.put(`/api/participants/${id}`, data);
      const updatedParticipant = response.data.data;
      
      // Update local state
      set(state => ({
        participants: state.participants.map(p => 
          p.id === id ? updatedParticipant : p
        )
      }));
      
      return updatedParticipant;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || 'Failed to update participant');
    }
  },

  deleteParticipant: async (id: string) => {
    try {
      await axios.delete(`/api/participants/${id}`);
      
      // Remove from local state
      set(state => ({
        participants: state.participants.filter(p => p.id !== id)
      }));
    } catch (error: any) {
      throw new Error(error.response?.data?.error || 'Failed to delete participant');
    }
  },
}));