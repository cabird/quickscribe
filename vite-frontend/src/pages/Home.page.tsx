import React, { useEffect, useState } from 'react';
import { ColorSchemeToggle } from '../components/ColorSchemeToggle/ColorSchemeToggle';
import { Container, Title, Text, Button, Group } from '@mantine/core';
import { Link } from 'react-router-dom';
import classes from './home.page.module.css';
import { IconFileText, IconUpload } from '@tabler/icons-react';
import { getApiVersion } from '@/api/util';

export function HomePage() {

  const [apiVersion, setApiVersion] = useState<string>('');

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
        <Title className={classes.title} ta="center" mt={100}>
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
