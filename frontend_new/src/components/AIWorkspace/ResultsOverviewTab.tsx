import { Grid, Box, Text, Group } from '@mantine/core';
import type { AnalysisResult } from '../../types';
import type { TabType } from './TabNavigation';
import { useAnalysisStore } from '../../stores/useAnalysisStore';

interface ResultsOverviewTabProps {
  analysisResults: AnalysisResult[];
  onSelectResult: (analysisType: AnalysisResult['analysisType']) => void;
}

export function ResultsOverviewTab({ analysisResults, onSelectResult }: ResultsOverviewTabProps) {
  const { getAnalysisTypeByName } = useAnalysisStore();
  const completedResults = analysisResults.filter(result => result.status === 'completed');
  
  if (completedResults.length === 0) {
    return (
      <Box ta="center" p="xl" style={{ color: 'var(--mantine-color-gray-5)' }}>
        <Box style={{ fontSize: '48px', opacity: 0.5, marginBottom: '15px' }}>
          📊
        </Box>
        <Text fw={600} size="md" mb="xs">
          No Analysis Results Yet
        </Text>
        <Text size="sm" c="dimmed">
          Use the Tools tab to generate analysis results from your transcript.
        </Text>
      </Box>
    );
  }

  const getTimeAgo = (createdAt: string) => {
    const now = new Date();
    const created = new Date(createdAt);
    const diffMs = now.getTime() - created.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min${diffMins === 1 ? '' : 's'} ago`;
    
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
    
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
  };

  const getPreviewText = (content: string, maxLength: number = 120) => {
    if (content.length <= maxLength) return content;
    return content.substring(0, maxLength).trim() + '...';
  };

  return (
    <Box p="md">
      <Grid>
        {completedResults.map((result) => (
          <Grid.Col key={`${result.analysisType}-${result.createdAt}`} span={{ base: 12, md: 6 }}>
            <Box
              onClick={() => onSelectResult(result.analysisType)}
              style={{
                border: '1px solid #e0e0e0',
                borderRadius: '8px',
                padding: '16px',
                backgroundColor: 'white',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#4a90e2';
                e.currentTarget.style.backgroundColor = '#f0f7ff';
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#e0e0e0';
                e.currentTarget.style.backgroundColor = 'white';
                e.currentTarget.style.boxShadow = 'none';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <Group justify="space-between" align="center" mb="sm">
                <Text fw={600} size="md" c="gray.8">
                  {getAnalysisTypeByName(result.analysisType)?.title || result.analysisType}
                </Text>
                <Text size="xs" c="gray.5">
                  {getTimeAgo(result.createdAt)}
                </Text>
              </Group>
              
              <Text
                size="sm"
                c="gray.6"
                style={{
                  lineHeight: 1.4,
                  flex: 1,
                  overflow: 'hidden',
                  display: '-webkit-box',
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical',
                }}
              >
                {getPreviewText(result.content)}
              </Text>
              
              {/* Click indicator */}
              <Group justify="flex-end" mt="xs">
                <Text size="xs" c="blue.6" fw={500}>
                  View details →
                </Text>
              </Group>
            </Box>
          </Grid.Col>
        ))}
      </Grid>
    </Box>
  );
}