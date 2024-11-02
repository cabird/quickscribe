// src/pages/RecordingsPage.tsx

import React, { useEffect, useState } from 'react';
import { fetchRecordings } from '../api/recordings';
import { Recording as RecordingModel } from '../interfaces/Models';
import Recording from '../components/Recording';

const RecordingsPage: React.FC = () => {
    const [recordings, setRecordings] = useState<RecordingModel[]>([]);

    useEffect(() => {
        fetchRecordings().then(setRecordings).catch(console.error);
    }, []);

    return (
        <div>
            <h1>Recordings</h1>
            <table>
                <thead>
                    <tr>
                        <th>Original Filename</th>
                        <th>Length</th>
                        <th>Transcription Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {recordings.map(recording => (
                        <Recording key={recording.id} recording={recording} />
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default RecordingsPage;

