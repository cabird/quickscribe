// src/components/AudioRecorder.tsx

import React, { useState, useRef } from 'react';
import { Button, Text, Tooltip } from '@mantine/core';
import { useAudioRecorder } from './useAudioRecorder';
import VolumeVisualizer from './VolumeVisualizer';
import { IconSquareFilled, IconPlayerRecordFilled } from '@tabler/icons-react';
import { RecordingCompleteDialog } from '../RecordingCompleteDialog';
import { notifications } from '@mantine/notifications';


interface AudioRecorderProps {
    onComplete: (finalAudioUrl: string) => void;
}

const AudioRecorder: React.FC<AudioRecorderProps> = ({ onComplete }) => {
    const { isRecording, volume, volumeHistory, recordingTime, isLoading, error, stopRecording, startRecording } = useAudioRecorder();

    const [showDialog, setShowDialog] = useState<boolean>(false);
    
    const handleStopRecording = async () => {
        stopRecording();
        setShowDialog(true);
    }

    const handleDialogSubmit = (data: { title: string, description: string }) => {
        console.log('dialog submit', data);
        // TODO: upload audio to server
        const finalAudioUrl = '';
        onComplete(finalAudioUrl);
        setShowDialog(false);
        notifications.show({ message: 'Recording saved' });
    }

    const formatTime = (seconds: number) => {
        const hours = Math.floor(seconds / 3600).toString().padStart(2, '0');
        const minutes = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
        const remainingSeconds = (seconds % 60).toString().padStart(2, '0');
        // show hours only if it's greater than 1 hour
        if (seconds > 3600) {
            return `${hours}:${minutes}:${remainingSeconds}`;
        } else {
            return `${minutes}:${remainingSeconds}`;
        } 
    }
    
    return (
        <div>
            {error && <Text c="red" mb="md">{error}</Text>}
            <Tooltip 
                label={isRecording ? "Stop Recording" : "Start Recording"}
                position="top"
            >
            <Button 
                variant="outline"
                loading={isLoading}
                onClick={isRecording ? handleStopRecording : startRecording}
                styles={(theme) => ({
                    root: {
                        color: theme.colors.red[6],
                        borderColor: 'transparent',
                        '&:hover': {
                            backgroundColor: `rgba(${theme.colors.red[6]}, 0.05)`,
                        },
                    },
                })}
                >
                {isRecording ? <IconSquareFilled /> : <IconPlayerRecordFilled />}
            </Button>
            </Tooltip>
            {
                isRecording && (
                    <VolumeVisualizer 
                        volumeHistory={volumeHistory} 
                        isRecording={isRecording} 
                    />
                )
            }
            {isRecording && (
                <>
                    <Text size="xl" style={{ marginTop: '1rem' }}>{formatTime(recordingTime)}</Text>
                    <Text>Recording in progress...</Text>
                </>
            )}
            <RecordingCompleteDialog
                isOpen={showDialog}
                onDiscard={() => {console.log('discard'); notifications.show({ message: 'Recording discarded' }); setShowDialog(false)}}
                onSubmit={handleDialogSubmit}
                recordingLength={recordingTime}
            />
            
        </div>
    );
};

export default AudioRecorder;
