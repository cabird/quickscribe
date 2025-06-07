import { Grid, Box, Text } from '@mantine/core';
import type { AnalysisResult, AnalysisType } from '../../types';
import { useAnalysisStore } from '../../stores/useAnalysisStore';
import { IconRenderer } from '../IconRenderer';


interface ToolsTabProps {
  analysisResults: AnalysisResult[];
  onRunAnalysis: (analysisType: AnalysisResult['analysisType']) => void;
}

export function ToolsTab({ analysisResults, onRunAnalysis }: ToolsTabProps) {
  const { analysisTypes, loading, error } = useAnalysisStore();
  const completedTypes = new Set(
    analysisResults.filter(result => result.status === 'completed').map(result => result.analysisType)
  );
  const pendingTypes = new Set(
    analysisResults.filter(result => result.status === 'pending').map(result => result.analysisType)
  );

  const getToolStatus = (toolName: string) => {
    if (pendingTypes.has(toolName)) return 'running';
    if (completedTypes.has(toolName)) return 'completed';
    return 'idle';
  };

  // Show loading state
  if (loading) {
    return (
      <Box p="md" style={{ textAlign: 'center', padding: '40px' }}>
        <Text size="lg" c="dimmed">Loading analysis tools...</Text>
      </Box>
    );
  }

  // Show error state  
  if (error) {
    return (
      <Box p="md" style={{ textAlign: 'center', padding: '40px' }}>
        <Text size="lg" c="red">Failed to load analysis tools</Text>
        <Text size="sm" c="dimmed" mt="xs">{error}</Text>
      </Box>
    );
  }

  // Show empty state
  if (analysisTypes.length === 0) {
    return (
      <Box p="md" style={{ textAlign: 'center', padding: '40px' }}>
        <Text size="lg" c="dimmed">No analysis tools available</Text>
      </Box>
    );
  }

  const renderTool = (analysisType: AnalysisType) => {
    const status = getToolStatus(analysisType.name);
    const isRunning = status === 'running';
    const isCompleted = status === 'completed';
    
    return (
      <Box
        key={analysisType.id}
        onClick={() => !isRunning && onRunAnalysis(analysisType.name)}
        style={{
          padding: '20px',
          border: `1px solid ${isCompleted ? '#4caf50' : isRunning ? '#ffc107' : '#e0e0e0'}`,
          borderRadius: '8px',
          backgroundColor: isCompleted ? '#e8f5e8' : isRunning ? '#fff3cd' : 'white',
          cursor: isRunning ? 'not-allowed' : 'pointer',
          textAlign: 'center',
          transition: 'all 0.2s ease',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '8px',
          minHeight: '120px',
        }}
        onMouseEnter={(e) => {
          if (!isRunning) {
            e.currentTarget.style.backgroundColor = isCompleted ? '#c8e6c9' : '#f0f7ff';
            e.currentTarget.style.borderColor = isCompleted ? '#388e3c' : '#4a90e2';
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
          }
        }}
        onMouseLeave={(e) => {
          if (!isRunning) {
            e.currentTarget.style.backgroundColor = isCompleted ? '#e8f5e8' : 'white';
            e.currentTarget.style.borderColor = isCompleted ? '#4caf50' : '#e0e0e0';
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'none';
          }
        }}
      >
        {/* Status indicator */}
        {isCompleted && (
          <Box
            style={{
              position: 'absolute',
              top: '8px',
              right: '8px',
              color: 'var(--mantine-color-green-6)',
              fontSize: '16px',
              fontWeight: 'bold',
            }}
          >
            ✓
          </Box>
        )}
        
        {/* Icon */}
        <Box style={{ 
          color: isRunning ? 'var(--mantine-color-yellow-6)' : isCompleted ? 'var(--mantine-color-green-6)' : 'var(--mantine-color-gray-6)',
          marginBottom: '4px'
        }}>
          {isRunning ? '⏳' : <IconRenderer iconName={analysisType.icon} size={24} />}
        </Box>
        
        {/* Title */}
        <Box style={{ 
          fontWeight: 600,
          fontSize: '14px',
          color: 'var(--mantine-color-gray-8)',
          marginBottom: '4px'
        }}>
          {isRunning ? 'Running...' : analysisType.title}
        </Box>
        
        {/* Description */}
        <Box style={{ 
          fontSize: '12px',
          color: 'var(--mantine-color-gray-6)',
          lineHeight: 1.3,
          textAlign: 'center'
        }}>
          {isRunning ? 'Processing transcript' : analysisType.description}
        </Box>
      </Box>
    );
  };

  return (
    <Box p="md">
      <Grid>
        {Array.isArray(analysisTypes) && analysisTypes.map(analysisType => (
          <Grid.Col key={analysisType.id} span={{ base: 12, sm: 6, md: 4 }}>
            {renderTool(analysisType)}
          </Grid.Col>
        ))}
      </Grid>
    </Box>
  );
}