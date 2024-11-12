// src/pages/RecordingsPage.tsx

import React, { useEffect, useState } from 'react';
import { fetchRecordings } from '../api/recordings';
import { Recording as RecordingModel } from '../interfaces/Models';
import Recording from '../components/Recording';
import { Container, Title, Table, Group, Button } from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import { IconHome, IconX } from '@tabler/icons-react';
import { Link } from 'react-router-dom';

const RecordingsPage: React.FC = () => {
    const [recordings, setRecordings] = useState<RecordingModel[]>([]);

    useEffect(() => {
        console.log("Fetching recordings");
        fetchRecordings()
            .then((data) => {
                console.log("Recordings fetched", data);
                setRecordings(Array.isArray(data) ? data : []);
            })
            .catch((error) => {
                console.error(error);
                showNotification({
                    title: 'Fetch Error',
                    message: 'Failed to load recordings. Please try again later.',
                    color: 'red',
                    icon: <IconX size={18} />, // Optional icon for error indication
                });
            });
    }, []);

    return (
        <Container>
            <Title order={1}>Recordings</Title>
            <Table>
                <thead>
                    <tr>
                        <th>Original Filename</th>
                        <th>Length</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {recordings.map(recording => (
                        <Recording key={recording.id} recording={recording} />
                    ))}
                </tbody>
            </Table>
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
        </Container>
    );
};

export default RecordingsPage;

