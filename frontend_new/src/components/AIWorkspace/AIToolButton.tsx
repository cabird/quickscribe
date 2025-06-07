import { Card, Stack, Text, Button, Progress } from '@mantine/core';
import { useState } from 'react';

interface AIToolButtonProps {
  icon: React.ReactNode;
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
        transition: 'all 300ms cubic-bezier(0.4, 0, 0.2, 1)',
        background: status === 'completed' 
          ? 'linear-gradient(135deg, rgba(64, 192, 87, 0.15), rgba(64, 192, 87, 0.08))'
          : status === 'processing'
          ? 'linear-gradient(135deg, rgba(255, 212, 59, 0.15), rgba(255, 212, 59, 0.08))'
          : 'linear-gradient(135deg, rgba(74, 144, 226, 0.12), rgba(74, 144, 226, 0.06))',
        backdropFilter: 'blur(12px)',
        border: `1px solid ${
          status === 'completed' ? 'rgba(64, 192, 87, 0.3)' :
          status === 'processing' ? 'rgba(255, 212, 59, 0.3)' :
          'rgba(74, 144, 226, 0.2)'
        }`,
        boxShadow: status === 'completed' 
          ? '0 8px 32px rgba(64, 192, 87, 0.2)' 
          : status === 'processing'
          ? '0 8px 32px rgba(255, 212, 59, 0.2)'
          : '0 6px 24px rgba(74, 144, 226, 0.15)',
      }}
      onClick={handleClick}
    >
      <Stack gap="sm" align="center" h="100%">
        <div>{icon}</div>
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