// src/components/RecordingCard.tsx

import React, { useEffect, useState } from 'react';
import { Recording as RecordingModel } from '../interfaces/Models';
import SpeakerLabelDialog from './SpeakerLabelDialog';
import { Card, Group, Text, Button, Tooltip, Stack, stylesToString } from '@mantine/core';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFileLines, faUserTag, faDownload, faTrashAlt, faTag } from '@fortawesome/free-solid-svg-icons';
import { faCopy, faFileAudio } from '@fortawesome/free-regular-svg-icons';
import { checkTranscriptionStatus, deleteRecording, deleteTranscription, fetchRecording, startTranscription } from '../api/recordings';
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
    const [currentRecording, setCurrentRecording] = useState<RecordingModel>(recording);

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
            fetch(`/api/ai/get_speaker_summaries/${recording.transcription_id}`)
                .then((response) => response.json())
                .then((data) => setSpeakerSummaries(data))
                .catch((error) => notifications.show({ title: 'Error', message: 'Failed to fetch speaker summaries', color: 'red' }));
        }
    }, [showSpeakerLabelDialog, recording.transcription_id]);

    // Update local state when props change
    useEffect(() => {
        setCurrentRecording(recording);
        setTranscriptionStatus(recording.transcription_status);
    }, [recording]);

    // Periodic check for transcription status if in progress
    useEffect(() => {
        let intervalId: number;
        if (transcriptionStatus === 'in_progress') {
            intervalId = window.setInterval(() => {
                checkTranscriptionStatus(recording.id).then((response) => {
                    if (response.status !== 'in_progress') {
                        clearInterval(intervalId);
                        setTranscriptionStatus(response.status);
                        
                        // If transcription is complete, fetch the updated recording
                        if (response.status === 'completed') {
                            fetchRecording(recording.id)
                                .then(updatedRecording => {
                                    // Update local state
                                    setCurrentRecording(updatedRecording);
                                    
                                    // Update the recording in-place by dispatching event
                                    window.dispatchEvent(new CustomEvent('recordingUpdated', { 
                                        detail: { recording: updatedRecording } 
                                    }));
                                    
                                    notifications.show({
                                        title: 'Transcription Complete',
                                        message: 'Your recording has been successfully transcribed',
                                        color: 'green'
                                    });
                                })
                                .catch(error => {
                                    console.error('Failed to fetch updated recording:', error);
                                    notifications.show({
                                        title: 'Error',
                                        message: 'Failed to fetch updated recording details',
                                        color: 'red'
                                    });
                                });
                        }
                    }
                });
            }, 15000); // Check every 15 seconds instead of 60 seconds
        }
        return () => clearInterval(intervalId);
    }, [recording.id, transcriptionStatus]);

    return (
        <Card shadow="sm" padding="lg" radius="md" withBorder className={styles.recordingCard}>
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div style={{ flex: 1 }}>
                    <Text fw={500}>{currentRecording.original_filename}</Text>
                    <Text size="sm" c="dimmed">Duration: {formatDuration(currentRecording.duration || 0)}</Text>
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
                            onClick={async () => {
                                const response = await startTranscription(recording.id);
                                showNotificationFromApiResponse(response);
                                
                                // Immediately fetch updated recording data
                                try {
                                    const updatedRecording = await fetchRecording(recording.id);
                                    setCurrentRecording(updatedRecording);
                                    setTranscriptionStatus(updatedRecording.transcription_status);
                                    
                                    // Also update parent component
                                    window.dispatchEvent(new CustomEvent('recordingUpdated', { 
                                        detail: { recording: updatedRecording } 
                                    }));
                                } catch (error) {
                                    console.error('Failed to fetch updated recording after starting transcription:', error);
                                }
                            }}
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
                            to={`/view_transcription/${transcriptionStatus === 'completed' ? currentRecording.transcription_id : -1}`}
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
                            href={`/api/ai/infer_speaker_names/${currentRecording.transcription_id}`}
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
