import axios from 'axios';
import { Recording } from '../interfaces/Models';
import { apiResponse } from '@/Common';

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

export const startTranscription = async (recordingId: string): Promise<apiResponse> => {
    try {
        const response = await axios.post(`/az_transcription/start_transcription/${recordingId}`);
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

// delete a recording
export const deleteRecording = async (recordingId: string): Promise<apiResponse> => {
    const response = await axios.get(`/api/delete_recording/${recordingId}`);
    // check if the response is successful
    if (response.status === 200) {
        //get the response in json
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

// delete a transcription
export const deleteTranscription = async (transcriptionId: string): Promise<apiResponse> => {
    const response = await axios.get(`/api/delete_transcription/${transcriptionId}`);
    // check if the response is successful
    if (response.status === 200) {
        //get the response in json
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

// check the status of a transcription
export const checkTranscriptionStatus = async (recordingId: string): Promise<{status: string, error: string}> => {
    const response = await axios.get<{status: string, error: string}>(`/az_transcription/check_transcription_status/${recordingId}`);
    if (response.status === 200) {
        // check if the response is successful
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

