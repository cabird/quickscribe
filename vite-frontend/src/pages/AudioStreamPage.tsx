// src/pages/AudioStreamPage.tsx

import React from 'react';
import { Container, Title, Button, Text } from '@mantine/core';
import AudioRecorder from '../components/AudioRecorder/AudioRecorder';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { IconHome } from '@tabler/icons-react';
export function AudioStreamPage() {
    const navigate = useNavigate();

    const handleRecordingComplete = (audioUrl: string) => {
        console.log('Recording complete:', audioUrl);
    };

    return (
        <Container 
            style={{ 
                minHeight: '100vh', 
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                textAlign: 'center' 
            }}
        >
            <Title order={2}>Start a New Recording</Title>
            <Text c="dimmed" mt="sm">Record audio directly from your browser.</Text>
            <AudioRecorder onComplete={handleRecordingComplete} />
            <Button
                    component={Link}
                    to="/"
                    variant="subtle"
                    leftSection={<IconHome size={16} />}
                >
                    Back to Home
                </Button>
        </Container>
    );
}

export default AudioStreamPage;