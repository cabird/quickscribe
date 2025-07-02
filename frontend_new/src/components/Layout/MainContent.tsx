import { Container, Group, Title, Button, SimpleGrid, Loader, Center, Text } from '@mantine/core';
import { LuGrid3X3, LuList } from 'react-icons/lu';
import { useUIStore } from '../../stores/useUIStore';
import { useRecordingStore } from '../../stores/useRecordingStore';
import { useTagStore } from '../../stores/useTagStore';
import { RecordingCard } from '../RecordingCard/RecordingCard';
import { useMemo } from 'react';
import type { Recording } from '../../types';

export function MainContent() {
  const { viewMode, setViewMode, filters } = useUIStore();
  const { recordings, loading } = useRecordingStore();
  const { tags } = useTagStore();

  // Filter recordings based on current filters
  const filteredRecordings = useMemo(() => {
    let filtered = recordings;

    // Filter by status
    if (filters.status !== 'all') {
      filtered = filtered.filter(recording => {
        switch (filters.status) {
          case 'recent':
            // Show recordings from last 7 days
            const weekAgo = new Date();
            weekAgo.setDate(weekAgo.getDate() - 7);
            return new Date(recording.upload_timestamp || 0) > weekAgo;
          case 'processing':
            return recording.transcription_status === 'in_progress' || 
                   recording.transcoding_status === 'in_progress' ||
                   recording.transcoding_status === 'queued';
          case 'completed':
            return recording.transcription_status === 'completed';
          default:
            return true;
        }
      });
    }

    // Filter by tags
    if (filters.tags.length > 0) {
      filtered = filtered.filter(recording => 
        recording.tagIds?.some(tagId => filters.tags.includes(tagId))
      );
    }

    // Filter by search
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter(recording =>
        (recording.title || recording.original_filename).toLowerCase().includes(searchLower)
      );
    }

    // Sort recordings by date (oldest first)
    // Priority: recorded_timestamp > upload_timestamp > end of list
    filtered.sort((a, b) => {
      const getTimestamp = (recording: Recording) => {
        return recording.recorded_timestamp || recording.upload_timestamp || null;
      };
      
      const timestampA = getTimestamp(a);
      const timestampB = getTimestamp(b);
      
      // If both have timestamps, sort by date (oldest first)
      if (timestampA && timestampB) {
        return new Date(timestampA).getTime() - new Date(timestampB).getTime();
      }
      
      // If only one has a timestamp, it goes first
      if (timestampA && !timestampB) return -1;
      if (!timestampA && timestampB) return 1;
      
      // If neither has timestamps, maintain original order
      return 0;
    });

    return filtered;
  }, [recordings, filters]);

  // Get current title based on active filters
  const getPageTitle = () => {
    if (filters.search) {
      return `Search: "${filters.search}"`;
    }
    
    switch (filters.status) {
      case 'recent':
        return 'Recent Recordings';
      case 'processing':
        return 'Processing';
      case 'completed':
        return 'Completed';
      default:
        return 'All Recordings';
    }
  };

  if (loading) {
    return (
      <Center h="50vh">
        <Loader size="xl" />
      </Center>
    );
  }

  return (
    <Container size="xl" py="md">
      {/* Header */}
      <Group justify="space-between" mb="xl">
        <Title order={1} c="dark">
          {getPageTitle()}
        </Title>
        
        <Group>
          <Button.Group>
            <Button
              variant={viewMode === 'grid' ? 'filled' : 'light'}
              onClick={() => setViewMode('grid')}
              leftSection={<LuGrid3X3 size={16} />}
            >
              Grid
            </Button>
            <Button
              variant={viewMode === 'list' ? 'filled' : 'light'}
              onClick={() => setViewMode('list')}
              leftSection={<LuList size={16} />}
            >
              List
            </Button>
          </Button.Group>
        </Group>
      </Group>

      {/* Recordings Grid/List */}
      {filteredRecordings.length === 0 ? (
        <Center py="xl">
          <Text c="dimmed" size="lg">
            {recordings.length === 0 
              ? 'No recordings yet. Upload your first recording to get started!'
              : 'No recordings match your current filters.'
            }
          </Text>
        </Center>
      ) : (
        <SimpleGrid
          cols={viewMode === 'grid' ? { base: 1, sm: 2, lg: 3 } : 1}
          spacing="md"
        >
          {filteredRecordings.map((recording) => (
            <RecordingCard 
              key={recording.id} 
              recording={recording}
              userTags={tags}
            />
          ))}
        </SimpleGrid>
      )}
    </Container>
  );
}