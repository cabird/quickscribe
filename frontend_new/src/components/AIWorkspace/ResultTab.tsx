import { Box, Text, Group, Button, ActionIcon } from '@mantine/core';
import { LuCopy, LuDownload, LuRefreshCw, LuTrash2 } from 'react-icons/lu';
import { notifications } from '@mantine/notifications';
import type { AnalysisResult } from '../../types';
import { useAnalysisStore } from '../../stores/useAnalysisStore';

interface ResultTabProps {
  analysisResult: AnalysisResult;
  onRerun?: (analysisType: AnalysisResult['analysisType']) => void;
  onDelete?: (analysisType: AnalysisResult['analysisType']) => void;
}

export function ResultTab({ analysisResult, onRerun, onDelete }: ResultTabProps) {
  const { getAnalysisTypeByName } = useAnalysisStore();
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(analysisResult.content);
      notifications.show({
        title: 'Copied',
        message: 'Analysis content copied to clipboard',
        color: 'green',
        autoClose: 3000,
      });
    } catch (error) {
      console.error('Failed to copy content:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to copy content',
        color: 'red',
        autoClose: 3000,
      });
    }
  };

  const handleExport = () => {
    const analysisType = getAnalysisTypeByName(analysisResult.analysisType);
    const title = analysisType?.title || analysisResult.analysisType;
    const blob = new Blob([`${title}\n${'='.repeat(title.length)}\n\n${analysisResult.content}`], { 
      type: 'text/plain' 
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.replace(/[^\w\s]/gi, '').trim()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    
    notifications.show({
      title: 'Exported',
      message: 'Analysis exported successfully',
      color: 'green',
      autoClose: 3000,
    });
  };

  const handleRerun = () => {
    if (onRerun) {
      onRerun(analysisResult.analysisType);
    }
  };

  const handleDelete = () => {
    if (onDelete) {
      onDelete(analysisResult.analysisType);
    }
  };

  const formatContent = (content: string) => {
    // Simple markdown-like formatting
    return content
      .split('\n')
      .map((line, index) => {
        // Headers (lines starting with #)
        if (line.startsWith('### ')) {
          return <Text key={index} size="md" fw={600} mb="xs" mt="md">{line.substring(4)}</Text>;
        }
        if (line.startsWith('## ')) {
          return <Text key={index} size="lg" fw={600} mb="xs" mt="lg">{line.substring(3)}</Text>;
        }
        if (line.startsWith('# ')) {
          return <Text key={index} size="xl" fw={700} mb="sm" mt="lg">{line.substring(2)}</Text>;
        }
        
        // Bold text (text surrounded by **)
        if (line.includes('**')) {
          const parts = line.split('**');
          return (
            <Text key={index} mb="xs" style={{ lineHeight: 1.6 }}>
              {parts.map((part, partIndex) => 
                partIndex % 2 === 1 ? <strong key={partIndex}>{part}</strong> : part
              )}
            </Text>
          );
        }
        
        // Bullet points (lines starting with • or -)
        if (line.match(/^[\s]*[•\-\*]\s/)) {
          return (
            <Text key={index} mb="xs" ml="md" style={{ lineHeight: 1.6 }}>
              {line.replace(/^[\s]*[•\-\*]\s/, '• ')}
            </Text>
          );
        }
        
        // Empty lines
        if (line.trim() === '') {
          return <Box key={index} style={{ height: '0.5rem' }} />;
        }
        
        // Regular paragraphs
        return <Text key={index} mb="xs" style={{ lineHeight: 1.6 }}>{line}</Text>;
      });
  };

  return (
    <Box p="md" style={{ height: '100%', overflow: 'auto' }}>
      {/* Header */}
      <Group justify="space-between" align="center" mb="md" pb="sm" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
        <Text size="lg" fw={600} c="gray.8">
          {getAnalysisTypeByName(analysisResult.analysisType)?.title || analysisResult.analysisType}
        </Text>
        <Group gap="xs">
          <ActionIcon size="sm" variant="subtle" onClick={handleCopy} title="Copy to clipboard">
            <LuCopy size={16} />
          </ActionIcon>
          <ActionIcon size="sm" variant="subtle" onClick={handleExport} title="Export as text file">
            <LuDownload size={16} />
          </ActionIcon>
          {onRerun && (
            <ActionIcon size="sm" variant="subtle" onClick={handleRerun} title="Re-run analysis">
              <LuRefreshCw size={16} />
            </ActionIcon>
          )}
          {onDelete && (
            <ActionIcon size="sm" variant="subtle" color="red" onClick={handleDelete} title="Delete analysis">
              <LuTrash2 size={16} />
            </ActionIcon>
          )}
        </Group>
      </Group>

      {/* Content */}
      <Box>
        {analysisResult.status === 'failed' ? (
          <Box ta="center" p="xl" style={{ color: 'var(--mantine-color-red-6)' }}>
            <Box style={{ fontSize: '48px', marginBottom: '15px' }}>⚠️</Box>
            <Text fw={600} size="md" mb="xs" c="red">
              Analysis Failed
            </Text>
            <Text size="sm" c="gray.6" mb="md">
              {analysisResult.errorMessage || 'An error occurred while processing this analysis.'}
            </Text>
            {onRerun && (
              <Button size="sm" variant="light" color="red" leftSection={<LuRefreshCw size={16} />} onClick={handleRerun}>
                Try Again
              </Button>
            )}
          </Box>
        ) : analysisResult.status === 'pending' ? (
          <Box ta="center" p="xl" style={{ color: 'var(--mantine-color-gray-5)' }}>
            <Box style={{ fontSize: '48px', marginBottom: '15px' }}>⏳</Box>
            <Text fw={600} size="md" mb="xs">
              Analysis in Progress
            </Text>
            <Text size="sm" c="dimmed">
              Please wait while we process your transcript...
            </Text>
          </Box>
        ) : (
          <Box style={{ color: 'var(--mantine-color-gray-8)' }}>
            {formatContent(analysisResult.content)}
          </Box>
        )}
      </Box>
    </Box>
  );
}