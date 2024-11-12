// src/components/Recording.tsx

// TODO: handle issue where the transcription status is updated and we don't have the transcription_id yet...

import React, { useCallback, useEffect, useState } from 'react';
import { Recording as RecordingModel } from '../interfaces/Models';
import SpeakerLabelDialog from './SpeakerLabelDialog';
import { Button, Container, Group, Tooltip } from '@mantine/core';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlay, faEye, faUserTag, faDownload, faCopy, faTrashAlt, faTag } from '@fortawesome/free-solid-svg-icons';
import './Recording.css';  // Import the new CSS file
import { checkTranscriptionStatus, deleteRecording, deleteTranscription, fetchRecording, startTranscription } from '../api/recordings';
import { notifications } from '@mantine/notifications';
import { IconAlertCircle, IconCheck, IconFileText, IconLoader } from '@tabler/icons-react';
import { formatDuration } from '../util';
import { showNotificationFromApiResponse, showNotificationFromError } from '@/Common';
import { Link } from 'react-router-dom';

interface RecordingProps {
    recording: RecordingModel;
    refreshTrigger?: boolean; // Optional prop to trigger a refresh of the recording
}

const Recording: React.FC<RecordingProps> = ({ recording, refreshTrigger }) => {
    const [showSpeakerLabelDialog, setShowSpeakerLabelDialog] = useState(false);
    const [speakerSummaries, setSpeakerSummaries] = useState<{ [key: string]: string } | null>(null);
    const [transcriptionStatus, setTranscriptionStatus] = useState<string>(recording.transcription_status);
    const [recordingData, setRecordingData] = useState<RecordingModel>(recording);

    const fetchUpdatedRecording = useCallback(async () => {
        try {
            const updatedRecording = await fetchRecording(recording.id);
            setRecordingData(updatedRecording);
        } catch (error) {
            console.error('Error fetching updated recording:', error);
            showNotificationFromError('Failed to fetch updated recording: ' + error);
        }
    }, [recording.id]);

    useEffect(() => {
        if (refreshTrigger) {
            fetchUpdatedRecording();
        }
    }, [refreshTrigger, fetchUpdatedRecording]);


    const copyTranscriptToClipboard = async (text: string) => {
        try {
            await navigator.clipboard.writeText(text);
            alert('Transcript copied to clipboard!');
        } catch (err) {
            console.error('Failed to copy text: ', err);
            showNotificationFromError('Failed to copy transcript to clipboard');
        }
    };

    const handleLabelSpeakers = () => {
        setShowSpeakerLabelDialog(true);
    };

    const handleDownload = () => {
        notifications.show({
            title: 'Downloading',
            message: 'Dummy Downloading recording message',
            color: 'blue'
        });
    }

    const handleDelete = async () => {
        //check if there is a transcription associated with this recording
        if (recording.transcription_id) {
            const response = await deleteTranscription(recording.transcription_id);
            showNotificationFromApiResponse(response);
        } else {
            const response = await deleteRecording(recording.id);
            showNotificationFromApiResponse(response);
        }
    };

    const handleAcceptSpeakerLabels = (speakerLabels: { [key: string]: string }) => {
        fetch(`/api/update_speaker_labels/${recording.transcription_id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(speakerLabels),
        }).then((response) => response.json())
        .then((data) => {
                console.log(data);
                alert('Speaker labels updated');
            }).then(fetchUpdatedRecording);
    };

    useEffect(() => {
        if (showSpeakerLabelDialog) {
            fetch(`/api/get_speaker_summaries/${recording.transcription_id}`)
                .then((response) => response.json())
                .then((data) => {
                    setSpeakerSummaries(data);
                })
                .catch((error) => {
                    console.error('Error fetching speaker summaries:', error);
                    alert('Failed to fetch speaker summaries');
                });
        }
    }, [showSpeakerLabelDialog, recording.transcription_id]);

    const transcription_text = "dummy";

    // if the transcription status is in_progress, check the status of the transcription and continue to check it once a minute until it no longer is in_progress
    useEffect(() => {
        let intervalId: number;
        if (recording.transcription_status === 'in_progress') {
            // Check immediately
            checkTranscriptionStatus(recording.id).then((response) => {
                if (response.error) {
                    notifications.show({
                        title: 'Error',
                        message: response.error,
                        color: 'red'
                    });
                }
                console.log("status is", response.status);
                if (response.status !== 'in_progress') {
                    clearInterval(intervalId);
                    setTranscriptionStatus(response.status);
                }
            });
            
            // Then check every minute
            intervalId = window.setInterval(() => {
                checkTranscriptionStatus(recording.id).then((response) => {
                    if (response.error) {
                        notifications.show({
                            title: 'Error',
                            message: response.error,
                            color: 'red'
                        });
                    }
                    console.log("status is", response.status);

                    if (response.status !== 'in_progress') {
                        clearInterval(intervalId);
                        setTranscriptionStatus(response.status);
                    }
                });
            }, 60000); // 60000ms = 1 minute
        }

        // Cleanup function to clear the interval when component unmounts
        // or when transcription_status changes
        return () => {
            if (intervalId) {
                clearInterval(intervalId);
            }
        };
    }, []);

    console.log(recording);

    return (
        <>
            <tr className="recording-row">
                <td>
                    <a href={`/download_recording/${recording.id}`} download>
                        {recording.original_filename}
                    </a>
                </td>
                <td>{formatDuration(recording.duration || 0)}</td>
                <td>
                    <Group   justify="center"> 
                        {transcriptionStatus === 'completed' && <Tooltip label="Transcription Completed"><span><IconCheck color='green' /></span></Tooltip>}
                        {transcriptionStatus === 'in_progress' && <Tooltip label="Transcription In Progress"><span><IconLoader color='blue' className='spinning_icon' /></span></Tooltip>}
                        {transcriptionStatus === 'not_started' && <Tooltip label="Transcription Not Started"><span ><IconAlertCircle /></span></Tooltip>}
                        {!['completed', 'in_progress', 'not_started'].includes(transcriptionStatus) && (
                        <span>Unknown Status ({transcriptionStatus}) {recording.transcription_error_message}</span>
                        )}
                    </Group>
                </td>
                <td className="icon-buttons">
                    <Tooltip label="Start Transcription">
                        <Button
                            onClick={() => startTranscription(recording.id)
                                .then((response) => {
                                    showNotificationFromApiResponse(response);
                                })  
                                .catch((error) => {
                                    showNotificationFromApiResponse({   
                                        status: 'error',
                                        error: 'Failed to start transcription: ' + error
                                    });
                                })}
                            disabled={transcriptionStatus === 'completed'}
                            variant="subtle"
                            className="icon-button"
                        >
                            <FontAwesomeIcon icon={faPlay} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="View Transcription">
                        <Button
                            component={Link}
                            to={`/view_transcription/${transcriptionStatus === 'completed' ? recording.transcription_id : -1}`}
                            disabled={transcriptionStatus !== 'completed'}
                            variant="subtle"
                            className="icon-button"
                        >
                            <IconFileText />
                        </Button>
                    </Tooltip>
                    <Tooltip label="Infer Speaker Names">
                        <Button
                            component="a"
                            href={`/infer_speaker_names/${recording.id}`}
                            disabled={transcriptionStatus !== 'completed'}
                            variant="subtle"
                            className="icon-button"
                        >
                            <FontAwesomeIcon icon={faUserTag} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="Download">
                        <Button
                            onClick={handleDownload}
                            disabled={transcriptionStatus === 'not_started'}
                            variant="subtle"
                            className="icon-button"
                        >
                            <FontAwesomeIcon icon={faDownload} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="Copy Transcript">
                        <Button
                            onClick={() => copyTranscriptToClipboard(transcription_text)}
                            disabled={transcriptionStatus !== 'completed'}
                            variant="subtle"
                            className="icon-button"
                        >
                            <FontAwesomeIcon icon={faCopy} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="Delete">
                        <Button
                            onClick={handleDelete}
                            variant="subtle"
                            className="icon-button"
                        >
                            <FontAwesomeIcon icon={faTrashAlt} />
                        </Button>
                    </Tooltip>
                    <Tooltip label="Label Speakers">
                        <Button
                            onClick={handleLabelSpeakers}
                            disabled={transcriptionStatus !== 'completed'}
                            variant="subtle"
                            className="icon-button"
                        >
                            <FontAwesomeIcon icon={faTag} />
                        </Button>
                    </Tooltip>
                </td>
            </tr>
            {showSpeakerLabelDialog && (
                <SpeakerLabelDialog 
                    speakerSummaries={speakerSummaries || {}}
                    isLoading={speakerSummaries === null}
                    onClose={() => setShowSpeakerLabelDialog(false)} 
                    onAccept={handleAcceptSpeakerLabels} 
                />
            )}
        </>
    );
};

export default Recording;
