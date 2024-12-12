import { Modal, TextInput, Textarea, Button, Group, Stack, Text } from '@mantine/core';
import React from 'react';

interface RecordingCompleteDialogProps {
  isOpen: boolean;
  onDiscard: () => void;
  onSubmit: (data: { title: string; description: string }) => void;
  recordingLength: number;
}

export function RecordingCompleteDialog({
  isOpen,
  onDiscard,
  onSubmit,
  recordingLength,
}: RecordingCompleteDialogProps) {
  const [title, setTitle] = React.useState('');
  const [description, setDescription] = React.useState('');

  const handleSubmit = () => {
    onSubmit({ title, description });
    setTitle('');
    setDescription('');
  };

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
    const remainingSeconds = (seconds % 60).toString().padStart(2, '0');
    return `${minutes}:${remainingSeconds}`;
  };

  return (
    <Modal opened={isOpen} onClose={onDiscard} title="Save Recording">
      <Stack>
        <TextInput
          label="Recording Title"
          placeholder="Enter a title"
          value={title}
          onChange={(e) => setTitle(e.currentTarget.value)}
          required
        />
        <Textarea
          label="Description"
          placeholder="Enter a brief description"
          value={description}
          onChange={(e) => setDescription(e.currentTarget.value)}
          minRows={3}
        />
        <Text size="sm" c="dimmed">Recording length: {formatTime(recordingLength)}</Text>
        
        <Group justify="flex-end" mt="md">
          <Button variant="light" color="red" onClick={onDiscard}>
            Discard
          </Button>
          <Button onClick={handleSubmit} disabled={!title}>
            Save Recording
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}