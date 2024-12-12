// src/components/RecordingCard.tsx

import React, { useEffect, useState } from 'react';
import { Recording as RecordingModel } from '../interfaces/Models';
import SpeakerLabelDialog from './SpeakerLabelDialog';
import { Card, Group, Text, Button, Tooltip, Stack, stylesToString } from '@mantine/core';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFileLines, faUserTag, faDownload, faTrashAlt, faTag } from '@fortawesome/free-solid-svg-icons';
import { faCopy, faFileAudio } from '@fortawesome/free-regular-svg-icons';
import { checkTranscriptionStatus, deleteRecording, deleteTranscription, startTranscription } from '../api/recordings';
import { notifications } from '@mantine/notifications';
import { IconAlertCircle, IconCheck, IconLoader } from '@tabler/icons-react';
import { formatDuration } from '../util';
import { showNotificationFromApiResponse } from '@/Common';
import { Link } from 'react-router-dom';
import styles from './RecordingCard.module.css';
import { IconProp } from '@fortawesome/fontawesome-svg-core';

interface RecordingProps {
    recording: RecordingModel;
    onDelete: (id: string) => void;
}

const RecordingCard: React.FC<RecordingProps> = ({ recording, onDelete }) => {
    const [showSpeakerLabelDialog, setShowSpeakerLabelDialog] = useState(false);
    const [speakerSummaries, setSpeakerSummaries] = useState<{ [key: string]: string } | null>(null);
    const [transcriptionStatus, setTranscriptionStatus] = useState<string>(recording.transcription_status);

    const copyTranscriptToClipboard = async (text: string) => {
        try {
            await navigator.clipboard.writeText(text);
            notifications.show({ title: 'Success', message: 'Transcript copied to clipboard!' });
        } catch (err) {
            console.error('Failed to copy text: ', err);
            notifications.show({ title: 'Error', message: 'Failed to copy transcript to clipboard', color: 'red' });
        }
    };

    const handleLabelSpeakers = () => setShowSpeakerLabelDialog(true);

    const handleDownload = () => {
        notifications.show({
            title: 'Downloading',
            message: 'Download started...',
            color: 'blue'
        });
    };

    const handleDelete = async () => {
        if (recording.transcription_id) {
            const response = await deleteTranscription(recording.transcription_id);
            showNotificationFromApiResponse(response);
        } else {
            const response = await deleteRecording(recording.id);
            showNotificationFromApiResponse(response);
        }
        onDelete(recording.id);
    };

    const handleAcceptSpeakerLabels = (speakerLabels: { [key: string]: string }) => {
        fetch(`/api/update_speaker_labels/${recording.transcription_id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(speakerLabels),
        })
        .then((response) => response.json())
        .then((data) => notifications.show({ title: 'Success', message: 'Speaker labels updated successfully' }));
    };

    useEffect(() => {
        if (showSpeakerLabelDialog) {
            fetch(`/api/get_speaker_summaries/${recording.transcription_id}`)
                .then((response) => response.json())
                .then((data) => setSpeakerSummaries(data))
                .catch((error) => notifications.show({ title: 'Error', message: 'Failed to fetch speaker summaries', color: 'red' }));
        }
    }, [showSpeakerLabelDialog, recording.transcription_id]);

    // Periodic check for transcription status if in progress
    useEffect(() => {
        let intervalId: number;
        if (recording.transcription_status === 'in_progress') {
            intervalId = window.setInterval(() => {
                checkTranscriptionStatus(recording.id).then((response) => {
                    if (response.status !== 'in_progress') {
                        clearInterval(intervalId);
                        setTranscriptionStatus(response.status);
                    }
                });
            }, 60000);
        }
        return () => clearInterval(intervalId);
    }, []);

    return (
        <Card shadow="sm" padding="lg" radius="md" withBorder className={styles.recordingCard}>
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div style={{ flex: 1 }}>
                    <Text fw={500}>{recording.original_filename}</Text>
                    <Text size="sm" c="dimmed">Duration: {formatDuration(recording.duration || 0)}</Text>
                    <Group gap="xs">            
                        <Text size="sm" c={transcriptionStatus === 'completed' ? 'green.6' : 
                                         transcriptionStatus === 'in_progress' ? 'blue.6' : 'gray.6'}>
                            {transcriptionStatus === 'completed' && "✓ Transcription Complete"}
                            {transcriptionStatus === 'in_progress' && "⟳ Processing..."}
                            {transcriptionStatus === 'not_started' && "• Not Started"}
                        </Text>
                    </Group>
                </div>

                <Group mt="auto" justify="flex-end" gap="xs" className={styles.actionButtons}>
                    <Tooltip label="Start Transcription">
                        <Button
                            onClick={() => startTranscription(recording.id).then(showNotificationFromApiResponse)}
                            disabled={transcriptionStatus === 'completed'}
                            variant="subtle"
                            size="sm"
                        >
                            <FontAwesomeIcon icon={faFileAudio as IconProp} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="View Transcription">
                        <Button
                            component={Link}
                            to={`/view_transcription/${transcriptionStatus === 'completed' ? recording.transcription_id : -1}`}
                            disabled={transcriptionStatus !== 'completed'}
                            variant="subtle"
                            size="sm"
                        >
                            <FontAwesomeIcon icon={faFileLines} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="Infer Speaker Names">
                        <Button
                            component="a"
                            href={`/infer_speaker_names/${recording.id}`}
                            disabled={transcriptionStatus !== 'completed'}
                            variant="subtle"
                            size="sm"
                        >
                            <FontAwesomeIcon icon={faUserTag} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="Download">
                        <Button onClick={handleDownload} disabled={transcriptionStatus === 'not_started'} variant="subtle" size="sm">
                            <FontAwesomeIcon icon={faDownload} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="Copy Transcript">
                        <Button onClick={() => copyTranscriptToClipboard("dummy text")} disabled={transcriptionStatus !== 'completed'} variant="subtle" size="xs">
                            <FontAwesomeIcon icon={faCopy as IconProp} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="Delete">
                        <Button onClick={handleDelete} variant="subtle" size="sm" color="red">
                            <FontAwesomeIcon icon={faTrashAlt} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="Label Speakers">
                        <Button onClick={handleLabelSpeakers} disabled={transcriptionStatus !== 'completed'} variant="subtle" size="sm">
                            <FontAwesomeIcon icon={faTag} />
                        </Button>
                    </Tooltip>
                </Group>
            </div>

            {showSpeakerLabelDialog && (
                <SpeakerLabelDialog
                    speakerSummaries={speakerSummaries || {}}
                    isLoading={speakerSummaries === null}
                    onClose={() => setShowSpeakerLabelDialog(false)}
                    onAccept={handleAcceptSpeakerLabels}
                />
            )}
        </Card>
    );
};

export default RecordingCard;
