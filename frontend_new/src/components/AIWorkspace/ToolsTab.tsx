import { Grid, Box, Text, Button, Group } from '@mantine/core';
import { useState } from 'react';
import type { AnalysisResult, AnalysisType } from '../../types';
import { useAnalysisStore } from '../../stores/useAnalysisStore';
import { IconRenderer } from '../IconRenderer';


interface ToolsTabProps {
  analysisResults: AnalysisResult[];
  onRunAnalysis: (analysisType: AnalysisResult['analysisType']) => void;
  onViewResult?: (analysisType: AnalysisResult['analysisType']) => void;
}

export function ToolsTab({ analysisResults, onRunAnalysis, onViewResult }: ToolsTabProps) {
  const { analysisTypes, loading, error } = useAnalysisStore();
  const [hoveredTool, setHoveredTool] = useState<string | null>(null);
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
    const isHovered = hoveredTool === analysisType.id;
    const showOverlay = isCompleted && isHovered && onViewResult;
    
    return (
      <Box
        key={analysisType.id}
        onClick={() => {
          if (isRunning) return;
          if (isCompleted && !isHovered) {
            // First click on completed tool shows overlay instead of running
            setHoveredTool(analysisType.id);
          } else if (!isCompleted) {
            onRunAnalysis(analysisType.name);
          }
        }}
        onMouseEnter={() => {
          if (isCompleted && onViewResult) {
            setHoveredTool(analysisType.id);
          }
        }}
        onMouseLeave={() => {
          setHoveredTool(null);
        }}
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
          transform: isHovered && !isRunning ? 'translateY(-2px)' : 'translateY(0)',
          boxShadow: isHovered && !isRunning ? '0 2px 8px rgba(0,0,0,0.1)' : 'none',
        }}
      >
        {/* Overlay for completed tools */}
        {showOverlay && (
          <Box
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              borderRadius: '8px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
              zIndex: 10,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <Text size="sm" fw={600} c="gray.8">
              Analysis Complete
            </Text>
            <Group gap="xs">
              <Button
                size="xs"
                variant="filled"
                color="blue"
                onClick={(e) => {
                  e.stopPropagation();
                  onViewResult(analysisType.name);
                  setHoveredTool(null);
                }}
              >
                View
              </Button>
              <Button
                size="xs"
                variant="outline"
                color="gray"
                onClick={(e) => {
                  e.stopPropagation();
                  onRunAnalysis(analysisType.name);
                  setHoveredTool(null);
                }}
              >
                Rerun
              </Button>
            </Group>
          </Box>
        )}

        {/* Status indicator */}
        {isCompleted && !showOverlay && (
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
          marginBottom: '4px',
          opacity: showOverlay ? 0.3 : 1,
        }}>
          {isRunning ? '⏳' : <IconRenderer iconName={analysisType.icon} size={24} />}
        </Box>
        
        {/* Title */}
        <Box style={{ 
          fontWeight: 600,
          fontSize: '14px',
          color: 'var(--mantine-color-gray-8)',
          marginBottom: '4px',
          minHeight: '20px', // Reserve space for title
          width: '100%',
          opacity: showOverlay ? 0.3 : 1,
        }}>
          {isRunning ? 'Running...' : analysisType.title}
        </Box>
        
        {/* Description */}
        <Box style={{ 
          fontSize: '12px',
          color: 'var(--mantine-color-gray-6)',
          lineHeight: 1.3,
          textAlign: 'center',
          minHeight: '32px', // Reserve space for description (2 lines)
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: showOverlay ? 0.3 : 1,
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