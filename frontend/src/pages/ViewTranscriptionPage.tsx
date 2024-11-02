// src/pages/ViewTranscriptionPage.tsx

import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Transcription } from '../interfaces/Models';

const ViewTranscriptionPage: React.FC = () => {
    const { transcriptionId } = useParams<{ transcriptionId: string }>();
    const [transcription, setTranscription] = useState<Transcription | null>(null);

    useEffect(() => {
        if (transcriptionId) {
            fetch(`/api/transcription/${transcriptionId}`)
                .then(response => response.json())
                .then(data => setTranscription(data))
                .catch(error => console.error('Error fetching transcription:', error));
        }
    }, [transcriptionId]);

    if (!transcription) {
        return <div>Loading...</div>;
    }

    return (
        <div>
            <h1>Transcription</h1>
            {transcription.diarized_transcript ? (
                <div>
                    <h3>Diarized Transcript:</h3>
                    <div>
                        {transcription.diarized_transcript.split('\n\n').map((segment, index) => (
                            <p key={index}>{segment}</p>
                        ))}
                    </div>
                </div>
            ) : (
                <p>No transcription text available.</p>
            )}
        </div>
    );
};

export default ViewTranscriptionPage;