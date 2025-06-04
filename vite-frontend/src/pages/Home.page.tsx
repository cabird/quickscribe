import React, { useEffect, useState } from 'react';
import { ColorSchemeToggle } from '../components/ColorSchemeToggle/ColorSchemeToggle';
import { Container, Title, Text, Button, Group } from '@mantine/core';
import { Link } from 'react-router-dom';
import classes from './home.page.module.css';
import { IconFileText, IconMicrophone, IconUpload, IconRefresh } from '@tabler/icons-react';
import { getApiVersion } from '@/api/util';
import { notifications } from '@mantine/notifications';

export function HomePage() {

  const [apiVersion, setApiVersion] = useState<string>('');
  const [syncLoading, setSyncLoading] = useState(false);

  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const version = await getApiVersion();
        setApiVersion(version);
      } catch (error) {
        console.error('Failed to fetch API version:', error);
      }
    };
    fetchVersion();
  }, []);

  const handlePlaudSync = async () => {
    setSyncLoading(true);
    try {
      const response = await fetch('/plaud/sync/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ dry_run: false }),
      });

      if (response.ok) {
        const data = await response.json();
        notifications.show({
          title: 'Plaud Sync Started',
          message: 'Your Plaud recordings are being synced in the background',
          color: 'green',
          icon: <IconRefresh size={16} />,
        });
      } else {
        const error = await response.json();
        notifications.show({
          title: 'Sync Failed',
          message: error.error || 'Failed to start Plaud sync',
          color: 'red',
        });
      }
    } catch (error) {
      console.error('Sync error:', error);
      notifications.show({
        title: 'Sync Failed',
        message: 'Network error while starting sync',
        color: 'red',
      });
    } finally {
      setSyncLoading(false);
    }
  };

  return (
    <div style={{ 
        background: 'linear-gradient(135deg, #f0f4f8 0%, #d9e4ec 100%)', 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        position: 'relative'
    }}>
      <Container style={{ textAlign: 'center' }}>
        <Title className={classes.title} ta="center" mt={50}>
          Welcome to{' '}
          <Text
            inherit
            variant="gradient"
            component="span"
            gradient={{ from: 'orange', to: 'yellow', deg: 45 }}
            className={classes.gradientText}
          >
            QuickScribe
          </Text>
        </Title>

        <Text c="dimmed" ta="center" size="lg" maw={580} mx="auto" mt="xl">
          Your go-to platform for audio transcription and file management.
        </Text>

        <Group justify="center" mt="xl" gap="md">
          <Button
            component={Link}
            to="/recordings"
            leftSection={<IconFileText size={18} />}
            style={{
              backgroundColor: '#1e90ff',
              color: '#fff',
              boxShadow: '0px 4px 12px rgba(0, 0, 0, 0.1)',
            }}
            onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#0073e6'}
            onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#1e90ff'}
          >
            View Recordings
          </Button>
          <Button
            component={Link}
            to="/upload"
            leftSection={<IconUpload size={18} />}
            style={{
              backgroundColor: '#28a745',
              color: '#fff',
              boxShadow: '0px 4px 12px rgba(0, 0, 0, 0.1)',
            }}
            onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#218838'}
            onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#28a745'}
          >
            Upload a New Recording
          </Button>
          <Button
            onClick={handlePlaudSync}
            loading={syncLoading}
            leftSection={<IconRefresh size={18} />}
            style={{
              backgroundColor: '#ff6b35',
              color: '#fff',
              boxShadow: '0px 4px 12px rgba(0, 0, 0, 0.1)',
            }}
            onMouseOver={(e) => !syncLoading && (e.currentTarget.style.backgroundColor = '#e55a2b')}
            onMouseOut={(e) => !syncLoading && (e.currentTarget.style.backgroundColor = '#ff6b35')}
          >
            Sync Plaud
          </Button>
        </Group>
      </Container>

      {apiVersion && (
        <Text
          size="xs"
          c="dimmed"
          style={{
            position: 'absolute',
            bottom: '1rem',
            right: '1rem',
            opacity: 0.7
          }}
        >
          API v{apiVersion}
        </Text>
      )}
    </div>
  );
}
