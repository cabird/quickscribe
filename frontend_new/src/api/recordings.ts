import axios from 'axios';
import type { Recording, ApiResponse, Transcription } from '../types';

export const fetchRecordings = async (): Promise<Recording[]> => {
    console.log("Fetching recordings");
    const response = await axios.get<Recording[]>('/api/recordings');
    console.log("Recordings fetched", response.data);
    return response.data;
};

export const fetchRecording = async (recordingId: string): Promise<Recording> => {
    const response = await axios.get<Recording>(`/api/recording/${recordingId}`);
    console.log("Recording fetched", response.data);
    return response.data;
};

export const startTranscription = async (recordingId: string): Promise<ApiResponse> => {
    try {
        await axios.post(`/az_transcription/start_transcription/${recordingId}`);
        return {
            status: 'success',
        };
    } catch (error: any) {
        console.error('Error starting transcription:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to start transcription'
        };
    }
};

export const deleteRecording = async (recordingId: string): Promise<ApiResponse> => {
    const response = await axios.get(`/api/delete_recording/${recordingId}`);
    if (response.status === 200) {
        const responseData = response.data;
        return {
            status: 'success',
            message: responseData.message
        };
    } else {
        return {
            status: 'error',
            error: 'Failed to delete recording'
        };
    }
};

export const deleteTranscription = async (transcriptionId: string): Promise<ApiResponse> => {
    const response = await axios.get(`/api/delete_transcription/${transcriptionId}`);
    if (response.status === 200) {
        const responseData = response.data;
        return {
            status: 'success',
            message: responseData.message
        };
    } else {
        return {
            status: 'error',
            error: 'Failed to delete transcription'
        };
    }
};

export const checkTranscriptionStatus = async (recordingId: string): Promise<{status: string, error: string}> => {
    const response = await axios.get<{status: string, error: string}>(`/az_transcription/check_transcription_status/${recordingId}`);
    if (response.status === 200) {
        if (response.data.error) {
            console.error("Error checking transcription status:", response.data.error);
            return {status: response.data.status, error: response.data.error};
        } else {
            return {status: response.data.status, error: ""};
        }
    } else {
        return {
            status: 'error',
            error: 'Failed to check transcription status'
        };
    }
};

export const uploadFile = async (file: File): Promise<ApiResponse> => {
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await axios.post('/api/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        
        return {
            status: 'success',
            message: response.data.message
        };
    } catch (error: any) {
        console.error('Error uploading file:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to upload file'
        };
    }
};

export const fetchTranscription = async (transcriptionId: string): Promise<Transcription> => {
    const response = await axios.get<Transcription>(`/api/transcription/${transcriptionId}`);
    console.log("Transcription fetched", response.data);
    return response.data;
};

export const triggerPostProcessing = async (recordingId: string): Promise<ApiResponse> => {
    try {
        const response = await axios.post(`/api/recording/${recordingId}/postprocess`);
        
        if (response.status === 200) {
            const responseData = response.data;
            return {
                status: 'success',
                message: responseData.status === 'completed' 
                    ? 'AI post-processing completed successfully'
                    : 'AI post-processing completed with some errors',
                data: responseData
            };
        } else {
            return {
                status: 'error',
                error: 'Failed to trigger post-processing'
            };
        }
    } catch (error: any) {
        console.error('Error triggering post-processing:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to trigger post-processing'
        };
    }
};

export const updateSpeakers = async (recordingId: string, speakerMapping: Record<string, string>): Promise<ApiResponse> => {
    try {
        const response = await axios.post(`/api/recording/${recordingId}/update_speakers`, speakerMapping);
        
        if (response.status === 200) {
            const responseData = response.data;
            return {
                status: 'success',
                message: responseData.message || 'Speaker mapping updated successfully',
                data: responseData
            };
        } else {
            return {
                status: 'error',
                error: 'Failed to update speakers'
            };
        }
    } catch (error: any) {
        console.error('Error updating speakers:', error);
        return {
            status: 'error',
            error: error.response?.data?.error || 'Failed to update speakers'
        };
    }
};

export const getSpeakerSummaries = async (transcriptionId: string): Promise<Record<string, string> | null> => {
    try {
        const response = await axios.get(`/api/ai/get_speaker_summaries/${transcriptionId}`);
        
        if (response.status === 200) {
            return response.data;
        } else {
            console.error('Failed to get speaker summaries:', response.status);
            return null;
        }
    } catch (error: any) {
        console.error('Error getting speaker summaries:', error);
        return null;
    }
};