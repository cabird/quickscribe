// src/components/Recording.tsx

import React, { useEffect, useState } from 'react';
import { Recording as RecordingModel } from '../interfaces/Models';
import SpeakerLabelDialog from './SpeakerLabelDialog';

interface RecordingProps {
    recording: RecordingModel;
}

const Recording: React.FC<RecordingProps> = ({ recording }) => {
    const [showSpeakerLabelDialog, setShowSpeakerLabelDialog] = useState(false);
    const [speakerSummaries, setSpeakerSummaries] = useState<{ [key: string]: string } | null>(null);

    const copyTranscriptToClipboard = async (text: string) => {
        try {
            await navigator.clipboard.writeText(text);
            alert('Transcript copied to clipboard!');
        } catch (err) {
            console.error('Failed to copy text: ', err);
            alert('Failed to copy transcript to clipboard');
        }
    };

    const handleLabelSpeakers = () => {
        setShowSpeakerLabelDialog(true);
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
            });
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

    console.log(recording);
    // TODO: Figure out the download_url
    // TODO: Figure out the transcription text
    // TODO: Add a link to the view_transcription route
    // TODO: Add a link to the infer_speaker_names route
    // TODO: Add a link to the delete_recording route
    return (
        <>

            <tr className="recording-row">
                <td>
                <a href = {`/download_recording/${recording.id}`} data-tooltip={recording.original_filename} download>
                    {recording.original_filename}
                </a>
            </td>
            <td>{recording.duration}</td>
            <td>
                {recording.transcription_status === 'completed' && <span>Completed</span>}
                {recording.transcription_status === 'in_progress' && <span>Transcription in Progress...</span>}
                {recording.transcription_status === 'not_started' && <span>Not Started</span>}
                {!['completed', 'in_progress', 'not_started'].includes(recording.transcription_status) && (
                    <span>Unknown Status ({recording.transcription_status}) {recording.transcription_error_message}</span>
                )}
            </td>
            <td className="actions">
                <span className={`icon ${recording.transcription_status === 'completed' ? 'disabled' : ''}`} data-tooltip="Start Transcription">
                    <a href={`/az_transcription_bp/start_transcription/${recording.id}`}>
                        <i className="fas fa-microphone"></i>
                    </a>
                </span>
                <span className={`icon ${recording.transcription_status !== 'completed' ? 'disabled' : ''}`} data-tooltip="View Transcription">
                    <a href={`/view_transcription/${recording.transcription_status === 'completed' ? recording.transcription_id : -1}`}>
                        <i className="fas fa-file-alt"></i>
                    </a>
                </span>
                <span className={`icon ${recording.transcription_status !== 'completed' ? 'disabled' : ''}`} data-tooltip="Infer Speaker Names">
                    <a href={`/infer_speaker_names/${recording.id}`}>
                        <i className="fas fa-users"></i>
                    </a>
                </span>
                <span className={`icon ${recording.transcription_status === 'not_started' ? 'disabled' : ''}`} data-tooltip="Download">
                    <a href={`/download_recording/${recording.id}`} download>
                        <i className="fas fa-download"></i>
                    </a>
                </span>
                <span className={`icon ${recording.transcription_status !== 'completed' ? 'disabled' : ''}`} data-tooltip="Copy Transcript">
                    <a href="#" onClick={() => copyTranscriptToClipboard(transcription_text)}>
                        <i className="fas fa-clipboard"></i>
                    </a>
                </span>
                <span className="icon" data-tooltip="Delete">
                    <a href={`/delete_recording/${recording.id}`}>
                        <i className="fas fa-trash-alt"></i>
                    </a>
                </span>
                <span className={`icon ${recording.transcription_status !== 'completed' ? 'disabled' : ''}`} data-tooltip="Label Speakers">
                    <a href="#" onClick={handleLabelSpeakers}>
                        <i className="fas fa-user-tag"></i>
                    </a>
                </span>
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