import axios from 'axios';

// get the api version
export const getApiVersion = async (): Promise<string> => {
    const response = await axios.get('/api/get_api_version');
    return response.data.version;
};