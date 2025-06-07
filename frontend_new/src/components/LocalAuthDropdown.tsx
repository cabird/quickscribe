import { useState, useEffect } from 'react';
import { Select, Button, Group, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconUser } from '@tabler/icons-react';

interface TestUser {
  id: string;
  name: string;
}

interface LocalAuthDropdownProps {
  onUserChange?: (user: TestUser | null) => void;
}

export function LocalAuthDropdown({ onUserChange }: LocalAuthDropdownProps) {
  const [testUsers, setTestUsers] = useState<TestUser[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resetting, setResetting] = useState<string | null>(null);

  // Only show this component if local auth is enabled
  if (!import.meta.env.VITE_LOCAL_AUTH) {
    return null;
  }

  // Load test users on component mount
  useEffect(() => {
    fetchTestUsers();
    // Load selected user from localStorage
    const savedUserId = localStorage.getItem('localAuthUserId');
    if (savedUserId) {
      setSelectedUserId(savedUserId);
    }
  }, []);

  const fetchTestUsers = async () => {
    try {
      const response = await fetch('/api/local/users');
      if (response.ok) {
        const users = await response.json();
        setTestUsers(users);
      } else {
        console.error('Failed to fetch test users');
      }
    } catch (error) {
      console.error('Error fetching test users:', error);
    }
  };

  const handleUserSelect = async (userId: string | null) => {
    if (!userId) {
      // Logout - clear selection
      setSelectedUserId(null);
      localStorage.removeItem('localAuthUserId');
      onUserChange?.(null);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/local/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      if (response.ok) {
        const data = await response.json();
        setSelectedUserId(userId);
        localStorage.setItem('localAuthUserId', userId);
        
        const selectedUser = testUsers.find(u => u.id === userId);
        onUserChange?.(selectedUser || null);
        
        notifications.show({
          title: 'Logged in',
          message: `Logged in as ${data.user.name}`,
          color: 'green',
          icon: <IconUser size={16} />,
        });
      } else {
        const error = await response.json();
        notifications.show({
          title: 'Login failed',
          message: error.error || 'Failed to login',
          color: 'red',
        });
      }
    } catch (error) {
      console.error('Login error:', error);
      notifications.show({
        title: 'Login failed',
        message: 'Network error',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleResetUser = async (userId: string) => {
    const user = testUsers.find(u => u.id === userId);
    if (!user || !confirm(`Reset all data for ${user.name}? This will delete all recordings and transcriptions.`)) {
      return;
    }

    setResetting(userId);
    try {
      const response = await fetch(`/api/local/reset-user/${userId}`, {
        method: 'POST',
      });

      if (response.ok) {
        const data = await response.json();
        notifications.show({
          title: 'User reset',
          message: `Reset ${user.name}: ${data.deleted_recordings} recordings, ${data.deleted_transcriptions} transcriptions deleted`,
          color: 'blue',
        });
        
        // Trigger data reload after reset
        window.dispatchEvent(new CustomEvent('userDataReset'));
      } else {
        const error = await response.json();
        notifications.show({
          title: 'Reset failed',
          message: error.error || 'Failed to reset user',
          color: 'red',
        });
      }
    } catch (error) {
      console.error('Reset error:', error);
      notifications.show({
        title: 'Reset failed',
        message: 'Network error',
        color: 'red',
      });
    } finally {
      setResetting(null);
    }
  };

  return (
    <Group align="center" gap="xs">
      <Text size="sm" c="dimmed">Test User:</Text>
      <Select
        placeholder="Select test user"
        data={[
          { value: '', label: 'None (Logout)' },
          ...testUsers.map(user => ({ value: user.id, label: user.name }))
        ]}
        value={selectedUserId}
        onChange={handleUserSelect}
        disabled={loading}
        w={200}
        size="sm"
      />
      {selectedUserId && (
        <Button
          variant="light"
          color="red"
          size="xs"
          leftSection={<IconTrash size={14} />}
          loading={resetting === selectedUserId}
          onClick={() => handleResetUser(selectedUserId)}
        >
          Reset Data
        </Button>
      )}
    </Group>
  );
}