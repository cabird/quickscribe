import { toast } from 'react-toastify';

export const showToast = {
  success: (message: string) => {
    toast.success(message);
  },

  error: (message: string) => {
    toast.error(message);
  },

  info: (message: string) => {
    toast.info(message);
  },

  warning: (message: string) => {
    toast.warning(message);
  },

  // Convenience methods for common scenarios
  apiError: (error: any) => {
    const message = error.response?.data?.error || error.message || 'An error occurred';
    toast.error(message);
  },

  recordingDeleted: () => {
    toast.success('Recording deleted successfully');
  },

  recordingUpdated: () => {
    toast.success('Recording updated successfully');
  },

  exportSuccess: () => {
    toast.success('Transcript exported successfully');
  },
};
