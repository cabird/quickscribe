import { Modal, TextInput, Button, Stack, Group, Text } from '@mantine/core';
import { useState } from 'react';
import { notifications } from '@mantine/notifications';
import { useParticipantStore } from '../../stores/participantStore';

interface AddParticipantModalProps {
  opened: boolean;
  onClose: () => void;
  onParticipantCreated: (participantId: string) => void;
  initialName?: string;
}

export function AddParticipantModal({ 
  opened, 
  onClose, 
  onParticipantCreated,
  initialName = ''
}: AddParticipantModalProps) {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [displayName, setDisplayName] = useState(initialName);
  const [email, setEmail] = useState('');
  const [organization, setOrganization] = useState('');
  const [role, setRole] = useState('');
  const [creating, setCreating] = useState(false);
  
  const { createParticipant } = useParticipantStore();

  // Auto-generate display name from first and last name
  const handleNameChange = (first: string, last: string) => {
    if (!displayName || displayName === `${firstName} ${lastName}`.trim()) {
      setDisplayName(`${first} ${last}`.trim());
    }
  };

  const handleSubmit = async () => {
    if (!displayName.trim()) {
      notifications.show({
        message: 'Display name is required',
        color: 'red',
      });
      return;
    }

    setCreating(true);
    try {
      const participant = await createParticipant({
        firstName: firstName.trim() || undefined,
        lastName: lastName.trim() || undefined,
        displayName: displayName.trim(),
        email: email.trim() || undefined,
        organization: organization.trim() || undefined,
        role: role.trim() || undefined,
      });

      notifications.show({
        message: `Created participant: ${participant.displayName}`,
        color: 'green',
      });

      onParticipantCreated(participant.id);
      handleClose();
    } catch (error) {
      console.error('Failed to create participant:', error);
      notifications.show({
        message: 'Failed to create participant',
        color: 'red',
      });
    } finally {
      setCreating(false);
    }
  };

  const handleClose = () => {
    // Reset form
    setFirstName('');
    setLastName('');
    setDisplayName('');
    setEmail('');
    setOrganization('');
    setRole('');
    onClose();
  };

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title="Add New Participant"
      size="md"
    >
      <Stack gap="md">
        <Group grow>
          <TextInput
            label="First Name"
            placeholder="John"
            value={firstName}
            onChange={(e) => {
              setFirstName(e.currentTarget.value);
              handleNameChange(e.currentTarget.value, lastName);
            }}
          />
          <TextInput
            label="Last Name"
            placeholder="Doe"
            value={lastName}
            onChange={(e) => {
              setLastName(e.currentTarget.value);
              handleNameChange(firstName, e.currentTarget.value);
            }}
          />
        </Group>

        <TextInput
          label="Display Name"
          placeholder="John Doe"
          value={displayName}
          onChange={(e) => setDisplayName(e.currentTarget.value)}
          required
          description="How this person's name will appear in transcripts"
        />

        <TextInput
          label="Email"
          placeholder="john.doe@example.com"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.currentTarget.value)}
        />

        <TextInput
          label="Organization"
          placeholder="Acme Corp"
          value={organization}
          onChange={(e) => setOrganization(e.currentTarget.value)}
        />

        <TextInput
          label="Role"
          placeholder="Software Engineer"
          value={role}
          onChange={(e) => setRole(e.currentTarget.value)}
        />

        <Group justify="flex-end" mt="md">
          <Button variant="subtle" onClick={handleClose}>
            Cancel
          </Button>
          <Button 
            onClick={handleSubmit} 
            loading={creating}
            disabled={!displayName.trim()}
            variant="filled"
            color="blue"
          >
            Create Participant
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}