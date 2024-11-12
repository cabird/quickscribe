import React, { useRef, useState } from 'react';
import { Container, Title, Button, Progress, Text, Group, Space, Alert } from '@mantine/core';
import { Dropzone, DropzoneProps, MIME_TYPES } from '@mantine/dropzone';
import { IconUpload, IconCheck, IconAlertCircle, IconFile, IconX, IconHome } from '@tabler/icons-react';
import { notifications, Notifications } from '@mantine/notifications';
import axios from 'axios';
import { Link } from 'react-router-dom';

const UploadPage: React.FC = () => {
    const [file, setFile] = useState<File | null>(null);
    const [progress, setProgress] = useState<number>(0);
    const [status, setStatus] = useState<string>('');
    const [error, setError] = useState<string | null>(null);

    const handleFileSelect = (selectedFiles: File[]) => {
        setError(null);
        setFile(selectedFiles[0]);  // Only allow one file at a time
    };

    const handleUpload = async () => {
        if (!file) {
            setError("Please select a file.");
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/upload', true);

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    setProgress(Math.round(percentComplete));
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    setStatus('File uploaded successfully!');
                    setProgress(0);
                    setError(null);
                } else {
                    setStatus('');
                    setProgress(0);
                    setError('Error uploading file: ' + xhr.statusText);
                }
            });

            xhr.addEventListener('error', () => {
                setStatus('');
                setProgress(0);
                setError('Error uploading file: ' + xhr.statusText);
            });

            xhr.send(formData);
        } catch (error) {
            console.error('Upload error:', error);
            setStatus('');
            setError('Error uploading file: ' + error);
            setProgress(0);
        }
    };

    const openRef = useRef<() => void>(null);

    return (
        <Container style={{ maxWidth: 500, marginTop: 50, textAlign: 'center' }}>
            <Title order={1} mb="md">Upload an Audio File</Title>

            <Dropzone
                openRef={openRef}
                onDrop={handleFileSelect}
                onReject={() => setError('File type not supported')}
                maxSize={100 * 1024 ** 2} // 10 MB max file size
                accept={{
                    'audio/mp3': ['.mp3'],
                    'audio/mp4': ['.m4a'],
                }}
                style={{ marginBottom: '1rem' }}
            >
                <div style={{ padding: '20px', textAlign: 'center' }}>
                    <Dropzone.Accept>
                        <IconFile size={50} stroke={1.5} color="green" />
                    </Dropzone.Accept>
                    <Dropzone.Reject>
                        <IconX size={50} stroke={1.5} color="red" />
                    </Dropzone.Reject>
                    <Dropzone.Idle>
                        <IconUpload size={50} stroke={1.5} />
                    </Dropzone.Idle>
                    <Text size="sm" mt="xs" c="dimmed">
                        Drag audio files here or click to select files
                    </Text>
                </div>
            </Dropzone>

            {file && (
                <Text size="sm" c="dimmed" mt="xs"> 
                    Selected file: {file.name}
                </Text>
            )}
            <Group justify="center" mt="md">
                <Button onClick={() => openRef.current?.()}
                    leftSection={<IconFile size={16} />}
                    style={{ width: '100%' }}
                >
                    Select files
                </Button>
            </Group>

            <Group justify="center" mt="md">
                <Button
                    color="blue"
                    leftSection={<IconUpload size={16} />}  
                    onClick={handleUpload}
                    style={{ width: '100%' }}
                >
                    Upload
                </Button>
            </Group>

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

            <Space h="md" />

            {progress > 0 && (
                <Progress
                    value={progress}
                    color={progress === 100 ? "green" : "blue"}
                    size="lg"
                    striped
                    animated
                    style={{ marginBottom: '1rem' }}
                />
            )}

            {status && (
                <Alert 
                    icon={<IconCheck size={16} />} 
                    title="Success" 
                    color="green"
                    withCloseButton
                    onClose={() => setStatus('')}
                >
                    {status}
                </Alert>
            )}

            {error && (
                <Alert 
                    icon={<IconAlertCircle size={16} />} 
                    title="Error" 
                    color="red"
                    withCloseButton
                    onClose={() => setError(null)}
                >
                    {error}
                </Alert>
            )}
        </Container>
    );
};

export default UploadPage;
