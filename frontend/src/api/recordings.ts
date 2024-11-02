import axios from 'axios';
import { Recording } from '../interfaces/Models';

export const fetchRecordings = async (): Promise<Recording[]> => {
    const response = await axios.get<Recording[]>('/api/recordings');
    return response.data;
};
