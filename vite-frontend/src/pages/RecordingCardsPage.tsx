// src/pages/RecordingCardsPage.tsx

import React, { useEffect, useState } from 'react';
import { fetchRecordings } from '../api/recordings';
import { Recording as RecordingModel } from '../interfaces/Models';
import RecordingCard from '../components/RecordingCard';
import { Container, Title, Loader, Group, Button } from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import { IconHome, IconX } from '@tabler/icons-react';
import styles from './RecordingCardsPage.module.css';
import { Link } from 'react-router-dom';

const RecordingCardsPage: React.FC = () => {
    const [recordings, setRecordings] = useState<RecordingModel[]>([]);
    const [loading, setLoading] = useState<boolean>(true);

    useEffect(() => {
        const loadRecordings = async () => {
            try {
                const data = await fetchRecordings();
                setRecordings(Array.isArray(data) ? data : []);
            } catch (error) {
                showNotification({
                    title: 'Fetch Error',
                    message: 'Failed to load recordings. Please try again later.',
                    color: 'red',
                    icon: <IconX size={18} />,
                });
            } finally {
                setLoading(false);
            }
        };

        loadRecordings();
    }, []);

    const handleDeleteRecording = (id: string) => {
        setRecordings((prev) => prev.filter((recording) => recording.id !== id));
    };

    return (
        <Container className={styles.pageContainer}>
            <Title order={1} className={styles.pageTitle}>Recordings</Title>
            <Group justify="center" mb="md">
                <Button
                    component={Link}
                    to="/"
                    variant="subtle"
                    leftSection={<IconHome size={16} />}
                >
                    Back to Home
                </Button>
            </Group>
            {loading ? (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                    <Loader size="lg" />
                </div>
            ) : (
                <div className={styles.gridContainer}>
                    {recordings.map((recording) => (
                        <RecordingCard
                            key={recording.id}
                            recording={recording}
                            onDelete={handleDeleteRecording}
                        />
                    ))}
                </div>
            )}
        </Container>
    );
};

export default RecordingCardsPage;
