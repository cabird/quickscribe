import { Modal, Stack, Group, Text, TextInput, Button, ActionIcon, ColorInput, rem } from '@mantine/core';
import { LuPlus, LuPencil, LuTrash2, LuCheck, LuX } from 'react-icons/lu';
import { useState } from 'react';
import { useTagStore } from '../../stores/useTagStore';
import { createTag, updateTag, deleteTag } from '../../api/tags';
import { showNotificationFromApiResponse } from '../../utils';
import { TagBadge } from './TagBadge';
import type { Tag } from '../../types';

interface TagManagerProps {
  onClose: () => void;
}

const DEFAULT_COLORS = [
  '#4DABF7', '#69DB7C', '#FFD43B', '#FF8787', '#DA77F2', 
  '#74C0FC', '#8CE99A', '#FFE066', '#FFA8A8', '#E599F7',
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'
];

export function TagManager({ onClose }: TagManagerProps) {
  const { tags, addTag, updateTag: updateTagStore, removeTag } = useTagStore();
  const [editingTag, setEditingTag] = useState<string | null>(null);
  const [newTagName, setNewTagName] = useState('');
  const [newTagColor, setNewTagColor] = useState(DEFAULT_COLORS[0]);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState('');
  const [loading, setLoading] = useState(false);

  const handleCreateTag = async () => {
    if (!newTagName.trim()) return;

    setLoading(true);
    try {
      const response = await createTag(newTagName.trim(), newTagColor);
      showNotificationFromApiResponse(response);
      
      if (response.status === 'success') {
        // Add optimistically to store
        const newTag: Tag = {
          id: Date.now().toString(), // Temporary ID
          name: newTagName.trim(),
          color: newTagColor,
        };
        addTag(newTag);
        
        setNewTagName('');
        setNewTagColor(DEFAULT_COLORS[0]);
      }
    } catch (error) {
      console.error('Error creating tag:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateTag = async (tagId: string) => {
    if (!editName.trim()) return;

    setLoading(true);
    try {
      const response = await updateTag(tagId, editName.trim(), editColor);
      showNotificationFromApiResponse(response);
      
      if (response.status === 'success') {
        // Update optimistically in store
        const updatedTag: Tag = {
          id: tagId,
          name: editName.trim(),
          color: editColor,
        };
        updateTagStore(updatedTag);
        
        setEditingTag(null);
        setEditName('');
        setEditColor('');
      }
    } catch (error) {
      console.error('Error updating tag:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTag = async (tagId: string) => {
    if (!confirm('Are you sure you want to delete this tag? It will be removed from all recordings.')) {
      return;
    }

    setLoading(true);
    try {
      const response = await deleteTag(tagId);
      showNotificationFromApiResponse(response);
      
      if (response.status === 'success') {
        removeTag(tagId);
      }
    } catch (error) {
      console.error('Error deleting tag:', error);
    } finally {
      setLoading(false);
    }
  };

  const startEditing = (tag: Tag) => {
    setEditingTag(tag.id);
    setEditName(tag.name);
    setEditColor(tag.color);
  };

  const cancelEditing = () => {
    setEditingTag(null);
    setEditName('');
    setEditColor('');
  };

  return (
    <Modal
      opened={true}
      onClose={onClose}
      title="Manage Tags"
      size="md"
    >
      <Stack gap="md">
        {/* Create New Tag */}
        <Stack gap="xs">
          <Text fw={500} size="sm">Create New Tag</Text>
          <Group>
            <TextInput
              placeholder="Tag name"
              value={newTagName}
              onChange={(e) => setNewTagName(e.currentTarget.value)}
              style={{ flex: 1 }}
              maxLength={32}
            />
            <ColorInput
              value={newTagColor}
              onChange={setNewTagColor}
              swatches={DEFAULT_COLORS}
              size="sm"
              style={{ width: rem(60) }}
            />
            <Button
              onClick={handleCreateTag}
              loading={loading}
              disabled={!newTagName.trim()}
              leftSection={<LuPlus size={16} />}
            >
              Add
            </Button>
          </Group>
        </Stack>

        {/* Existing Tags */}
        <Stack gap="xs">
          <Text fw={500} size="sm">Existing Tags ({tags.length})</Text>
          
          {tags.length === 0 ? (
            <Text size="sm" c="dimmed" ta="center" py="md">
              No tags created yet. Create your first tag above.
            </Text>
          ) : (
            <Stack gap="xs">
              {tags.map((tag) => (
                <Group key={tag.id} justify="space-between" p="xs" style={{ 
                  borderRadius: rem(6),
                  backgroundColor: editingTag === tag.id ? 'var(--mantine-color-gray-0)' : 'transparent',
                }}>
                  {editingTag === tag.id ? (
                    // Edit mode
                    <>
                      <Group style={{ flex: 1 }}>
                        <TextInput
                          value={editName}
                          onChange={(e) => setEditName(e.currentTarget.value)}
                          size="sm"
                          style={{ flex: 1 }}
                          maxLength={32}
                        />
                        <ColorInput
                          value={editColor}
                          onChange={setEditColor}
                          swatches={DEFAULT_COLORS}
                          size="sm"
                          style={{ width: rem(60) }}
                        />
                      </Group>
                      <Group gap="xs">
                        <ActionIcon
                          size="sm"
                          color="green"
                          onClick={() => handleUpdateTag(tag.id)}
                          loading={loading}
                          disabled={!editName.trim()}
                        >
                          <LuCheck size={14} />
                        </ActionIcon>
                        <ActionIcon
                          size="sm"
                          color="gray"
                          onClick={cancelEditing}
                          disabled={loading}
                        >
                          <LuX size={14} />
                        </ActionIcon>
                      </Group>
                    </>
                  ) : (
                    // View mode
                    <>
                      <TagBadge tag={tag} />
                      <Group gap="xs">
                        <ActionIcon
                          size="sm"
                          variant="subtle"
                          color="gray"
                          onClick={() => startEditing(tag)}
                        >
                          <LuPencil size={14} />
                        </ActionIcon>
                        <ActionIcon
                          size="sm"
                          variant="subtle"
                          color="red"
                          onClick={() => handleDeleteTag(tag.id)}
                        >
                          <LuTrash2 size={14} />
                        </ActionIcon>
                      </Group>
                    </>
                  )}
                </Group>
              ))}
            </Stack>
          )}
        </Stack>
      </Stack>
    </Modal>
  );
}