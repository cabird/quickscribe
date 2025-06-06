import { notifications } from '@mantine/notifications';
import type { ApiResponse } from '../types';

export const formatDuration = (seconds: number): string => {
    if (!seconds || seconds === 0) return '0:00';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
    
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
};

export const showNotificationFromApiResponse = (response: ApiResponse) => {
    if (response.status === 'success') {
        notifications.show({
            title: 'Success',
            message: response.message || 'Operation completed successfully',
            color: 'green'
        });
    } else {
        notifications.show({
            title: 'Error',
            message: response.error || 'An error occurred',
            color: 'red'
        });
    }
};

export const getStatusColor = (status?: string) => {
    switch (status) {
        case 'completed':
            return 'green';
        case 'in_progress':
            return 'blue';
        case 'failed':
            return 'red';
        case 'queued':
            return 'yellow';
        default:
            return 'gray';
    }
};

export const getStatusText = (status?: string) => {
    switch (status) {
        case 'completed':
            return '✓ Transcription Complete';
        case 'in_progress':
            return '⟳ Processing...';
        case 'failed':
            return '✗ Failed';
        case 'queued':
            return '⏳ Queued';
        case 'not_started':
        default:
            return '• Not Started';
    }
};

// Custom event for recording updates (preserve existing functionality)
export const dispatchRecordingUpdate = (recording: any) => {
    window.dispatchEvent(new CustomEvent('recordingUpdated', { 
        detail: { recording } 
    }));
};