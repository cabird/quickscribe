import { Card, Stack, Text, Button, Progress } from '@mantine/core';
import { useState } from 'react';

interface AIToolButtonProps {
  icon: string;
  title: string;
  description: string;
  onComplete: () => void;
}

export function AIToolButton({ icon, title, description, onComplete }: AIToolButtonProps) {
  const [status, setStatus] = useState<'idle' | 'processing' | 'completed'>('idle');
  const [progress, setProgress] = useState(0);

  const handleClick = () => {
    if (status !== 'idle') return;

    setStatus('processing');
    setProgress(0);

    // Simulate processing with progress
    const interval = setInterval(() => {
      setProgress(prev => {
        const next = prev + Math.random() * 15 + 5;
        if (next >= 100) {
          clearInterval(interval);
          setStatus('completed');
          setTimeout(() => {
            onComplete();
            // Reset after a delay
            setTimeout(() => {
              setStatus('idle');
              setProgress(0);
            }, 2000);
          }, 500);
          return 100;
        }
        return next;
      });
    }, 200);
  };

  const getButtonColor = () => {
    switch (status) {
      case 'processing':
        return 'yellow';
      case 'completed':
        return 'green';
      default:
        return 'blue';
    }
  };

  const getButtonText = () => {
    switch (status) {
      case 'processing':
        return `Processing... ${Math.floor(progress)}%`;
      case 'completed':
        return '✅ Generated';
      default:
        return 'Generate';
    }
  };

  return (
    <Card
      withBorder
      radius="md"
      style={{
        cursor: status === 'idle' ? 'pointer' : 'default',
        transition: 'all 200ms ease',
        background: status === 'completed' 
          ? 'linear-gradient(135deg, var(--mantine-color-green-0) 0%, var(--mantine-color-green-1) 100%)'
          : status === 'processing'
          ? 'linear-gradient(135deg, var(--mantine-color-yellow-0) 0%, var(--mantine-color-yellow-1) 100%)'
          : 'linear-gradient(135deg, var(--mantine-color-blue-0) 0%, var(--mantine-color-blue-1) 100%)',
        '&:hover': {
          transform: status === 'idle' ? 'translateY(-2px)' : 'none',
          boxShadow: status === 'idle' ? 'var(--mantine-shadow-md)' : 'none',
        },
      }}
      onClick={handleClick}
    >
      <Stack gap="sm" align="center" h="100%">
        <Text size="xl">{icon}</Text>
        <Text fw={600} size="sm" ta="center">
          {title}
        </Text>
        <Text size="xs" c="dimmed" ta="center" style={{ flex: 1 }}>
          {description}
        </Text>
        
        {status === 'processing' && (
          <Progress value={progress} size="sm" w="100%" color="yellow" />
        )}
        
        <Button
          size="xs"
          color={getButtonColor()}
          variant={status === 'completed' ? 'light' : 'filled'}
          disabled={status === 'processing'}
          loading={status === 'processing'}
          fullWidth
        >
          {getButtonText()}
        </Button>
      </Stack>
    </Card>
  );
}