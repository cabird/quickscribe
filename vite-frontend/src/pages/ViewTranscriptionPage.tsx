// src/pages/ViewTranscriptionPage.tsx
import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Transcription } from '../interfaces/Models';
import { Container, Title, Text, Button, Group } from '@mantine/core';
import styles from './ViewTranscriptionPage.module.css';
import { IconFileText, IconHome } from '@tabler/icons-react';

const ViewTranscriptionPage: React.FC = () => {
    const { transcriptionId } = useParams<{ transcriptionId: string }>();
    const [transcription, setTranscription] = useState<Transcription | null>(null);

    useEffect(() => {
        if (transcriptionId) {
            fetch(`/api/transcription/${transcriptionId}`)
                .then((response) => response.json())
                .then((data) => setTranscription(data))
                .catch((error) => console.error('Error fetching transcription:', error));
        }
    }, [transcriptionId]);

    if (!transcription) {
        return <Text>Loading...</Text>;
    }

    return (
        <Container>
            <Title order={1} className="title">Transcription</Title>
            <Group justify="center" mb="md">
                <Button
                    component={Link}
                    to="/recordings"
                    variant="subtle"
                    leftSection={<IconFileText size={16} />}
                >
                    Back to Recordings
                </Button>
            </Group>
            {transcription.diarized_transcript ? (
                <div>
                    <Title order={3} className="subtitle">Diarized Transcript:</Title>
                    <div>
                        {transcription.diarized_transcript.split('\n\n').map((segment, index) => {
                            const [speaker, ...dialogue] = segment.split(': ');
                            return (
                                <div key={index} className={`${styles.dialogue} ${index % 2 === 0 ? styles.odd : styles.even}`}>
                                    <span className={styles.speaker}>{speaker}:</span>
                                    <span className={styles.dialogueText}>{dialogue.join(': ')}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            ) : (
                <Text>No transcription text available.</Text>
            )}
        </Container>
    );
};

export default ViewTranscriptionPage;
