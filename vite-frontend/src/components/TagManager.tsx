import React, { useState, useEffect } from 'react';
import {
    Modal,
    Button,
    Group,
    Stack,
    TextInput,
    ColorInput,
    Title,
    ActionIcon,
    Table,
    Text,
    Loader
} from '@mantine/core';
import { IconEdit, IconTrash, IconPlus } from '@tabler/icons-react';
import { Tag } from '../interfaces/Models';
import { fetchUserTags, createTag, updateTag, deleteTag } from '../api/tags';
import { notifications } from '@mantine/notifications';
import { showNotificationFromApiResponse } from '@/Common';
import TagBadge from './TagBadge';

interface TagManagerProps {
    opened: boolean;
    onClose: () => void;
    onTagsUpdated?: () => void;
}

const TagManager: React.FC<TagManagerProps> = ({ opened, onClose, onTagsUpdated }) => {
    const [tags, setTags] = useState<Tag[]>([]);
    const [loading, setLoading] = useState(true);
    const [editingTag, setEditingTag] = useState<Tag | null>(null);
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [formData, setFormData] = useState({ name: '', color: '#4444FF' });

    const loadTags = async () => {
        try {
            setLoading(true);
            const userTags = await fetchUserTags();
            setTags(userTags);
        } catch (error) {
            notifications.show({
                title: 'Error',
                message: 'Failed to load tags',
                color: 'red'
            });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (opened) {
            loadTags();
        }
    }, [opened]);

    const handleCreateTag = async () => {
        if (!formData.name.trim()) {
            notifications.show({
                title: 'Validation Error',
                message: 'Tag name is required',
                color: 'red'
            });
            return;
        }

        const response = await createTag(formData.name.trim(), formData.color);
        showNotificationFromApiResponse(response);
        
        if (response.status === 'success') {
            setFormData({ name: '', color: '#4444FF' });
            setShowCreateForm(false);
            loadTags();
            onTagsUpdated?.();
        }
    };

    const handleUpdateTag = async () => {
        if (!editingTag || !formData.name.trim()) return;

        const response = await updateTag(editingTag.id, formData.name.trim(), formData.color);
        showNotificationFromApiResponse(response);
        
        if (response.status === 'success') {
            setEditingTag(null);
            setFormData({ name: '', color: '#4444FF' });
            loadTags();
            onTagsUpdated?.();
        }
    };

    const handleDeleteTag = async (tagId: string) => {
        if (!confirm('Are you sure you want to delete this tag? It will be removed from all recordings.')) {
            return;
        }

        const response = await deleteTag(tagId);
        showNotificationFromApiResponse(response);
        
        if (response.status === 'success') {
            loadTags();
            onTagsUpdated?.();
        }
    };

    const startEditing = (tag: Tag) => {
        setEditingTag(tag);
        setFormData({ name: tag.name, color: tag.color });
        setShowCreateForm(false);
    };

    const startCreating = () => {
        setShowCreateForm(true);
        setEditingTag(null);
        setFormData({ name: '', color: '#4444FF' });
    };

    const cancelEditing = () => {
        setEditingTag(null);
        setShowCreateForm(false);
        setFormData({ name: '', color: '#4444FF' });
    };

    const isFormValid = formData.name.trim().length > 0;

    return (
        <Modal
            opened={opened}
            onClose={onClose}
            title="Manage Tags"
            size="md"
        >
            <Stack gap="md">
                {/* Create/Edit Form */}
                {(showCreateForm || editingTag) && (
                    <Stack gap="sm" p="md" style={{ backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                        <Title order={5}>
                            {editingTag ? 'Edit Tag' : 'Create New Tag'}
                        </Title>
                        <TextInput
                            label="Tag Name"
                            placeholder="Enter tag name"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            maxLength={32}
                        />
                        <ColorInput
                            label="Color"
                            value={formData.color}
                            onChange={(color) => setFormData({ ...formData, color })}
                            format="hex"
                            swatches={['#4444FF', '#BB44BB', '#44BB44', '#FF5733', '#FFA500', '#800080', '#008080', '#FF1493']}
                        />
                        <Group>
                            <Button
                                onClick={editingTag ? handleUpdateTag : handleCreateTag}
                                disabled={!isFormValid}
                                size="sm"
                            >
                                {editingTag ? 'Update' : 'Create'}
                            </Button>
                            <Button
                                variant="subtle"
                                onClick={cancelEditing}
                                size="sm"
                            >
                                Cancel
                            </Button>
                        </Group>
                    </Stack>
                )}

                {/* Create Button */}
                {!showCreateForm && !editingTag && (
                    <Button
                        leftSection={<IconPlus size={16} />}
                        onClick={startCreating}
                        variant="light"
                    >
                        Create New Tag
                    </Button>
                )}

                {/* Tags List */}
                {loading ? (
                    <Group justify="center">
                        <Loader size="sm" />
                    </Group>
                ) : tags.length === 0 ? (
                    <Text c="dimmed" ta="center">No tags created yet</Text>
                ) : (
                    <Table>
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th>Tag</Table.Th>
                                <Table.Th>Actions</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {tags.map((tag) => (
                                <Table.Tr key={tag.id}>
                                    <Table.Td>
                                        <TagBadge tag={tag} />
                                    </Table.Td>
                                    <Table.Td>
                                        <Group gap="xs">
                                            <ActionIcon
                                                variant="subtle"
                                                color="blue"
                                                onClick={() => startEditing(tag)}
                                                size="sm"
                                            >
                                                <IconEdit size={16} />
                                            </ActionIcon>
                                            <ActionIcon
                                                variant="subtle"
                                                color="red"
                                                onClick={() => handleDeleteTag(tag.id)}
                                                size="sm"
                                            >
                                                <IconTrash size={16} />
                                            </ActionIcon>
                                        </Group>
                                    </Table.Td>
                                </Table.Tr>
                            ))}
                        </Table.Tbody>
                    </Table>
                )}
            </Stack>
        </Modal>
    );
};

export default TagManager;