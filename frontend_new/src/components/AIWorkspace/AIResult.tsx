import { Card, Group, Text, Button, ActionIcon, Textarea } from '@mantine/core';
import { IconCopy, IconDownload, IconEdit, IconTrash, IconCheck, IconX } from '@tabler/icons-react';
import { useState } from 'react';
import { notifications } from '@mantine/notifications';

interface AIResultProps {
  title: string;
  content: string;
  onRemove: () => void;
}

export function AIResult({ title, content, onRemove }: AIResultProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(content);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      notifications.show({
        title: 'Copied',
        message: 'Content copied to clipboard',
        color: 'green'
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to copy content',
        color: 'red'
      });
    }
  };

  const handleExport = () => {
    const blob = new Blob([`${title}\n${'='.repeat(title.length)}\n\n${content}`], { 
      type: 'text/plain' 
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.replace(/[^\w\s]/gi, '').trim()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    
    notifications.show({
      title: 'Exported',
      message: 'Content exported successfully',
      color: 'green'
    });
  };

  const handleSaveEdit = () => {
    setIsEditing(false);
    // In a real app, you'd save the changes to the backend
    notifications.show({
      title: 'Saved',
      message: 'Changes saved successfully',
      color: 'green'
    });
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditContent(content);
  };

  return (
    <Card withBorder radius="md" style={{ borderLeft: '4px solid var(--mantine-color-blue-6)' }}>
      <Group justify="space-between" align="flex-start" mb="sm">
        <Text fw={600} size="md">
          {title}
        </Text>
        <Group gap="xs">
          <ActionIcon size="sm" variant="subtle" onClick={handleCopy}>
            <IconCopy size={14} />
          </ActionIcon>
          <ActionIcon size="sm" variant="subtle" onClick={() => setIsEditing(!isEditing)}>
            <IconEdit size={14} />
          </ActionIcon>
          <ActionIcon size="sm" variant="subtle" onClick={handleExport}>
            <IconDownload size={14} />
          </ActionIcon>
          <ActionIcon size="sm" variant="subtle" color="red" onClick={onRemove}>
            <IconTrash size={14} />
          </ActionIcon>
        </Group>
      </Group>

      {isEditing ? (
        <>
          <Textarea
            value={editContent}
            onChange={(e) => setEditContent(e.currentTarget.value)}
            minRows={4}
            autosize
            mb="sm"
          />
          <Group gap="xs">
            <Button size="xs" leftSection={<IconCheck size={14} />} onClick={handleSaveEdit}>
              Save
            </Button>
            <Button size="xs" variant="light" leftSection={<IconX size={14} />} onClick={handleCancelEdit}>
              Cancel
            </Button>
          </Group>
        </>
      ) : (
        <Text size="sm" style={{ whiteSpace: 'pre-line', lineHeight: 1.6 }}>
          {content}
        </Text>
      )}
    </Card>
  );
}