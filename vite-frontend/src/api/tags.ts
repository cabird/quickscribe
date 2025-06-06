import axios from 'axios';
import { Tag, Recording } from '../interfaces/Models';
import { apiResponse } from '@/Common';

// Get all tags for the current user
export const fetchUserTags = async (): Promise<Tag[]> => {
    console.log("Fetching user tags");
    const response = await axios.get<Tag[]>('/api/tags/get');
    console.log("User tags fetched", response.data);
    return response.data;
};

// Create a new tag
export const createTag = async (name: string, color: string): Promise<apiResponse> => {
    try {
        const response = await axios.post('/api/tags/create', {
            name,
            color
        });
        return {
            status: 'success',
            message: 'Tag created successfully',
            data: response.data
        };
    } catch (error: any) {
        console.error('Error creating tag:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to create tag'
        };
    }
};

// Update an existing tag
export const updateTag = async (tagId: string, name?: string, color?: string): Promise<apiResponse> => {
    try {
        const updateData: any = { tagId };
        if (name) updateData.name = name;
        if (color) updateData.color = color;
        
        const response = await axios.post('/api/tags/update', updateData);
        return {
            status: 'success',
            message: 'Tag updated successfully',
            data: response.data
        };
    } catch (error: any) {
        console.error('Error updating tag:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to update tag'
        };
    }
};

// Delete a tag
export const deleteTag = async (tagId: string): Promise<apiResponse> => {
    try {
        const response = await axios.get(`/api/tags/delete/${tagId}`);
        return {
            status: 'success',
            message: response.data.message || 'Tag deleted successfully'
        };
    } catch (error: any) {
        console.error('Error deleting tag:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to delete tag'
        };
    }
};

// Add a tag to a recording
export const addTagToRecording = async (recordingId: string, tagId: string): Promise<apiResponse> => {
    try {
        const response = await axios.get(`/api/recordings/${recordingId}/add_tag/${tagId}`);
        return {
            status: 'success',
            message: 'Tag added to recording',
            data: response.data
        };
    } catch (error: any) {
        console.error('Error adding tag to recording:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to add tag to recording'
        };
    }
};

// Remove a tag from a recording
export const removeTagFromRecording = async (recordingId: string, tagId: string): Promise<apiResponse> => {
    try {
        const response = await axios.get(`/api/recordings/${recordingId}/remove_tag/${tagId}`);
        return {
            status: 'success',
            message: 'Tag removed from recording',
            data: response.data
        };
    } catch (error: any) {
        console.error('Error removing tag from recording:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to remove tag from recording'
        };
    }
};