import axios from 'axios';
import type { Participant, CreateParticipantRequest } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '';

// Get all participants for the current user
export const getParticipants = async (): Promise<Participant[]> => {
    try {
        const response = await axios.get(`${API_BASE}/api/participants`);
        if (response.status === 200 && response.data.status === 'success') {
            return response.data.data || [];
        }
        throw new Error(response.data.error || 'Failed to fetch participants');
    } catch (error) {
        console.error('Error fetching participants:', error);
        throw error;
    }
};

// Create a new participant
export const createParticipant = async (data: CreateParticipantRequest): Promise<Participant> => {
    try {
        const response = await axios.post(`${API_BASE}/api/participants`, data);
        if ((response.status === 200 || response.status === 201) && response.data.status === 'success') {
            return response.data.data;
        }
        throw new Error(response.data.error || 'Failed to create participant');
    } catch (error) {
        console.error('Error creating participant:', error);
        throw error;
    }
};

// Search participants by name
export const searchParticipants = async (query: string, fuzzy = true): Promise<Participant[]> => {
    try {
        const response = await axios.get(`${API_BASE}/api/participants/search`, {
            params: { query, fuzzy }
        });
        if (response.status === 200 && response.data.status === 'success') {
            return response.data.data || [];
        }
        throw new Error(response.data.error || 'Failed to search participants');
    } catch (error) {
        console.error('Error searching participants:', error);
        throw error;
    }
};