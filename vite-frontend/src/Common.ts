import { notifications } from "@mantine/notifications";

//create a response object for the delete functions
export interface apiResponse {
    status: string;
    message?: string;
    error?: string;
}

// write a function to handle the response and show the notifications
export const showNotificationFromApiResponse = (response: apiResponse) => {
    if (response.status === 'success') {
        notifications.show({
            title: 'Success',
            message: response.message || 'Operation successful',
            color: 'green'
        });
    } else {
        notifications.show({
            title: 'Error',
            message: response.error || 'Operation failed',
            color: 'red'
        });
    }
};


export const showNotificationFromError = (error: string) => {
    notifications.show({
        title: 'Error',
        message: error,
        color: 'red'
    });
};