import { Stack, Text, TextInput, UnstyledButton, Group, Badge, Button, rem } from '@mantine/core';
import { LuSearch, LuMusic, LuClock, LuSettings, LuCheck, LuPlus } from 'react-icons/lu';
import { useUIStore } from '../../stores/useUIStore';
import { useRecordingStore } from '../../stores/useRecordingStore';
import { useTagStore } from '../../stores/useTagStore';
import { TagManager } from '../Tags/TagManager';
import { useState } from 'react';

const statusFilters = [
  { value: 'all', label: 'All Recordings', icon: LuMusic, color: 'blue' },
  { value: 'recent', label: 'Recent', icon: LuClock, color: 'green' },
  { value: 'processing', label: 'Processing', icon: LuSettings, color: 'yellow' },
  { value: 'completed', label: 'Completed', icon: LuCheck, color: 'teal' },
];

export function BrowseTab() {
  const { filters, setFilters } = useUIStore();
  const { recordings } = useRecordingStore();
  const { tags } = useTagStore();
  const [showTagManager, setShowTagManager] = useState(false);

  // Count recordings for each filter
  const getFilterCount = (filterValue: string) => {
    switch (filterValue) {
      case 'all':
        return recordings.length;
      case 'recent':
        const weekAgo = new Date();
        weekAgo.setDate(weekAgo.getDate() - 7);
        return recordings.filter(r => new Date(r.upload_timestamp || 0) > weekAgo).length;
      case 'processing':
        return recordings.filter(r => 
          r.transcription_status === 'in_progress' || 
          r.transcoding_status === 'in_progress' ||
          r.transcoding_status === 'queued'
        ).length;
      case 'completed':
        return recordings.filter(r => r.transcription_status === 'completed').length;
      default:
        return 0;
    }
  };

  // Count recordings for each tag
  const getTagCount = (tagId: string) => {
    return recordings.filter(r => r.tagIds?.includes(tagId)).length;
  };

  const handleTagToggle = (tagId: string) => {
    const currentTags = filters.tags;
    const newTags = currentTags.includes(tagId)
      ? currentTags.filter(id => id !== tagId)
      : [...currentTags, tagId];
    
    setFilters({ tags: newTags });
  };

  return (
    <Stack gap="md">
      <Text fw={600} size="lg">Browse & Filter</Text>
      
      {/* Search */}
      <TextInput
        placeholder="Search recordings..."
        leftSection={<LuSearch size={16} />}
        value={filters.search}
        onChange={(e) => setFilters({ search: e.currentTarget.value })}
        styles={{
          input: {
            borderRadius: rem(8),
          },
        }}
      />

      {/* Status Filters */}
      <Stack gap="xs">
        <Text fw={500} size="sm" c="dark">Status</Text>
        <Stack gap={2}>
          {statusFilters.map((filter) => {
            const Icon = filter.icon;
            const isActive = filters.status === filter.value;
            const count = getFilterCount(filter.value);
            
            return (
              <UnstyledButton
                key={filter.value}
                onClick={() => setFilters({ status: filter.value })}
                style={{
                  padding: rem(8),
                  borderRadius: rem(6),
                  backgroundColor: isActive ? 'var(--mantine-color-blue-light)' : 'transparent',
                  color: isActive ? 'var(--mantine-color-blue-filled)' : 'var(--mantine-color-gray-7)',
                  transition: 'all 200ms ease',
                  '&:hover': {
                    backgroundColor: isActive ? 'var(--mantine-color-blue-light)' : 'var(--mantine-color-gray-0)',
                  },
                }}
              >
                <Group justify="space-between">
                  <Group gap="xs">
                    <Icon size={16} />
                    <Text size="sm" fw={isActive ? 500 : 400}>
                      {filter.label}
                    </Text>
                  </Group>
                  <Badge 
                    size="sm" 
                    variant={isActive ? 'filled' : 'light'}
                    color={isActive ? 'blue' : 'gray'}
                  >
                    {count}
                  </Badge>
                </Group>
              </UnstyledButton>
            );
          })}
        </Stack>
      </Stack>

      {/* Tags Section */}
      <Stack gap="xs">
        <Group justify="space-between">
          <Text fw={500} size="sm" c="dark">Tags</Text>
          <Button 
            size="xs" 
            variant="light"
            leftSection={<LuPlus size={12} />}
            onClick={() => setShowTagManager(true)}
          >
            Manage
          </Button>
        </Group>
        
        <Stack gap={2}>
          {tags.map((tag) => {
            const isActive = filters.tags.includes(tag.id);
            const count = getTagCount(tag.id);
            
            return (
              <UnstyledButton
                key={tag.id}
                onClick={() => handleTagToggle(tag.id)}
                style={{
                  padding: rem(6),
                  borderRadius: rem(6),
                  backgroundColor: isActive ? 'var(--mantine-color-blue-light)' : 'transparent',
                  transition: 'all 200ms ease',
                  '&:hover': {
                    backgroundColor: isActive ? 'var(--mantine-color-blue-light)' : 'var(--mantine-color-gray-0)',
                  },
                }}
              >
                <Group justify="space-between">
                  <Group gap="xs">
                    <div
                      style={{
                        width: 12,
                        height: 12,
                        borderRadius: '50%',
                        backgroundColor: tag.color,
                        border: '2px solid white',
                        boxShadow: '0 0 0 1px rgba(0,0,0,0.1)',
                      }}
                    />
                    <Text 
                      size="sm" 
                      fw={isActive ? 500 : 400}
                      c={isActive ? 'blue' : 'dark'}
                    >
                      {tag.name}
                    </Text>
                  </Group>
                  <Badge 
                    size="xs" 
                    variant={isActive ? 'filled' : 'light'}
                    color={isActive ? 'blue' : 'gray'}
                  >
                    {count}
                  </Badge>
                </Group>
              </UnstyledButton>
            );
          })}
        </Stack>

        {tags.length === 0 && (
          <Text size="sm" c="dimmed" ta="center" py="md">
            No tags yet. Create your first tag to organize your recordings.
          </Text>
        )}
      </Stack>

      {showTagManager && (
        <TagManager onClose={() => setShowTagManager(false)} />
      )}
    </Stack>
  );
}