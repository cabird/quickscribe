import axios from 'axios';
import type { Tag, ApiResponse } from '../types';

export const fetchTags = async (): Promise<Tag[]> => {
    console.log("Fetching tags");
    const response = await axios.get<Tag[]>('/api/tags/get');
    console.log("Tags fetched", response.data);
    return response.data;
};

export const createTag = async (name: string, color: string): Promise<ApiResponse> => {
    try {
        await axios.post('/api/tags/create', { name, color });
        return {
            status: 'success',
            message: 'Tag created successfully'
        };
    } catch (error: any) {
        console.error('Error creating tag:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to create tag'
        };
    }
};

export const updateTag = async (tagId: string, name?: string, color?: string): Promise<ApiResponse> => {
    try {
        const payload: any = { tagId };
        if (name !== undefined) payload.name = name;
        if (color !== undefined) payload.color = color;
        
        await axios.post('/api/tags/update', payload);
        return {
            status: 'success',
            message: 'Tag updated successfully'
        };
    } catch (error: any) {
        console.error('Error updating tag:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to update tag'
        };
    }
};

export const deleteTag = async (tagId: string): Promise<ApiResponse> => {
    try {
        await axios.get(`/api/tags/delete/${tagId}`);
        return {
            status: 'success',
            message: 'Tag deleted successfully'
        };
    } catch (error: any) {
        console.error('Error deleting tag:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to delete tag'
        };
    }
};

export const addTagToRecording = async (recordingId: string, tagId: string): Promise<ApiResponse> => {
    try {
        await axios.get(`/api/recordings/${recordingId}/add_tag/${tagId}`);
        return {
            status: 'success',
            message: 'Tag added to recording'
        };
    } catch (error: any) {
        console.error('Error adding tag to recording:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to add tag to recording'
        };
    }
};

export const removeTagFromRecording = async (recordingId: string, tagId: string): Promise<ApiResponse> => {
    try {
        await axios.get(`/api/recordings/${recordingId}/remove_tag/${tagId}`);
        return {
            status: 'success',
            message: 'Tag removed from recording'
        };
    } catch (error: any) {
        console.error('Error removing tag from recording:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to remove tag from recording'
        };
    }
};