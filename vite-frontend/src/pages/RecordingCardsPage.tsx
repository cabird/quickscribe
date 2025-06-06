// src/pages/RecordingCardsPage.tsx

import React, { useEffect, useState } from 'react';
import { fetchRecordings } from '../api/recordings';
import { fetchUserTags } from '../api/tags';
import { Recording as RecordingModel, Tag } from '../interfaces/Models';
import RecordingCard from '../components/RecordingCard';
import TagManager from '../components/TagManager';
import { Container, Title, Loader, Group, Button, MultiSelect, Text } from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import { IconHome, IconX, IconSettings } from '@tabler/icons-react';
import styles from './RecordingCardsPage.module.css';
import { Link } from 'react-router-dom';

const RecordingCardsPage: React.FC = () => {
    const [recordings, setRecordings] = useState<RecordingModel[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [userTags, setUserTags] = useState<Tag[]>([]);
    const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
    const [showTagManager, setShowTagManager] = useState(false);

    useEffect(() => {
        const loadData = async () => {
            try {
                const [recordingsData, tagsData] = await Promise.all([
                    fetchRecordings(),
                    fetchUserTags()
                ]);
                setRecordings(Array.isArray(recordingsData) ? recordingsData : []);
                setUserTags(Array.isArray(tagsData) ? tagsData : []);
            } catch (error) {
                showNotification({
                    title: 'Fetch Error',
                    message: 'Failed to load data. Please try again later.',
                    color: 'red',
                    icon: <IconX size={18} />,
                });
            } finally {
                setLoading(false);
            }
        };

        loadData();
        
        // Listen for recording update events (this is triggered by the RecordingCard component, when the transcription is complete, for instance)
        const handleRecordingUpdated = (event: CustomEvent) => {
            const updatedRecording = event.detail.recording;
            // Update the recording in-place to maintain order
            setRecordings(prev => 
                prev.map(rec => rec.id === updatedRecording.id ? updatedRecording : rec)
            );
        };
        
        window.addEventListener('recordingUpdated', handleRecordingUpdated as EventListener);
        
        return () => {
            window.removeEventListener('recordingUpdated', handleRecordingUpdated as EventListener);
        };
    }, []);

    const handleDeleteRecording = (id: string) => {
        setRecordings((prev) => prev.filter((recording) => recording.id !== id));
    };

    // Filter recordings based on selected tags
    const filteredRecordings = selectedTagIds.length === 0 
        ? recordings 
        : recordings.filter(recording => 
            recording.tagIds && recording.tagIds.some(tagId => selectedTagIds.includes(tagId))
        );

    // Reload tags when tag manager updates
    const handleTagsUpdated = async () => {
        try {
            const tagsData = await fetchUserTags();
            setUserTags(Array.isArray(tagsData) ? tagsData : []);
        } catch (error) {
            console.error('Failed to reload tags:', error);
        }
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
                <Button
                    variant="subtle"
                    leftSection={<IconSettings size={16} />}
                    onClick={() => setShowTagManager(true)}
                >
                    Manage Tags
                </Button>
            </Group>

            {/* Tag Filtering */}
            {userTags.length > 0 && (
                <Group mb="md" justify="center">
                    <MultiSelect
                        label="Filter by tags"
                        placeholder="Select tags to filter"
                        data={userTags.map(tag => ({ value: tag.id, label: tag.name }))}
                        value={selectedTagIds}
                        onChange={setSelectedTagIds}
                        clearable
                        searchable
                        size="sm"
                        style={{ minWidth: 300 }}
                    />
                    {selectedTagIds.length > 0 && (
                        <Text size="sm" c="dimmed">
                            Showing {filteredRecordings.length} of {recordings.length} recordings
                        </Text>
                    )}
                </Group>
            )}
            {loading ? (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                    <Loader size="lg" />
                </div>
            ) : (
                <div className={styles.gridContainer}>
                    {filteredRecordings.map((recording) => (
                        <RecordingCard
                            key={recording.id}
                            recording={recording}
                            onDelete={handleDeleteRecording}
                            userTags={userTags}
                        />
                    ))}
                </div>
            )}

            <TagManager 
                opened={showTagManager}
                onClose={() => setShowTagManager(false)}
                onTagsUpdated={handleTagsUpdated}
            />
        </Container>
    );
};

export default RecordingCardsPage;
