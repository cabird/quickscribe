import { Modal, Grid, Stack, Text, Group, Button, Badge, Card, Divider, Loader, Center } from '@mantine/core';
import { 
  LuEye, 
  LuCopy, 
  LuFileText,
  LuRocket,
  LuChartBar,
  LuSearch,
  LuListTodo,
  LuCircleHelp,
  LuSmile,
  LuTag,
  LuList
} from 'react-icons/lu';
import { notifications } from '@mantine/notifications';
import { useUIStore } from '../../stores/useUIStore';
import { useRecordingStore } from '../../stores/useRecordingStore';
import { useTagStore } from '../../stores/useTagStore';
import { formatDuration, getStatusText } from '../../utils';
import { TagBadge } from '../Tags/TagBadge';
import { AIToolButton } from './AIToolButton';
import { AIResult } from './AIResult';
import { fetchTranscription } from '../../api/recordings';
import { useState, useEffect } from 'react';
import type { Transcription } from '../../types';

export function AIWorkspaceModal() {
  const { aiWorkspace, closeAIWorkspace } = useUIStore();
  const { getRecordingById } = useRecordingStore();
  const { getTagsByIds } = useTagStore();
  
  const [results, setResults] = useState<Array<{id: string, type: string, title: string, content: string}>>([]);
  const [transcription, setTranscription] = useState<Transcription | null>(null);
  const [transcriptionLoading, setTranscriptionLoading] = useState(false);

  const recording = getRecordingById(aiWorkspace.recordingId || '');
  
  if (!recording) {
    return null;
  }

  const recordingTags = getTagsByIds(recording.tagIds || []);

  // Fetch transcription when modal opens
  useEffect(() => {
    if (recording?.transcription_id && aiWorkspace.isOpen) {
      setTranscriptionLoading(true);
      fetchTranscription(recording.transcription_id)
        .then(setTranscription)
        .catch(error => {
          console.error('Failed to fetch transcription:', error);
          setTranscription(null);
        })
        .finally(() => setTranscriptionLoading(false));
    } else {
      setTranscription(null);
    }
  }, [recording?.transcription_id, aiWorkspace.isOpen]);

  const handleToolComplete = (type: string, title: string, content: string) => {
    const newResult = {
      id: Date.now().toString(),
      type,
      title,
      content
    };
    setResults(prev => [...prev, newResult]);
  };

  const handleRemoveResult = (resultId: string) => {
    setResults(prev => prev.filter(r => r.id !== resultId));
  };

  const handleCopyTranscript = async () => {
    if (!transcription) return;
    
    try {
      let textToCopy = '';
      
      if (transcription.diarized_transcript) {
        // For diarized transcripts, extract clean text without HTML formatting
        textToCopy = transcription.diarized_transcript
          .split('\n')
          .map(line => {
            // Parse speaker lines and format them cleanly
            const speakerMatch = line.match(/^([^:]+):\s*(.*)$/);
            if (speakerMatch) {
              return `${speakerMatch[1]}: ${speakerMatch[2]}`;
            }
            return line;
          })
          .filter(line => line.trim()) // Remove empty lines
          .join('\n');
      } else if (transcription.text) {
        textToCopy = transcription.text;
      }
      
      await navigator.clipboard.writeText(textToCopy);
      notifications.show({
        title: 'Copied!',
        message: 'Transcript copied to clipboard',
        color: 'green',
        autoClose: 3000,
      });
    } catch (error) {
      console.error('Failed to copy transcript:', error);
      notifications.show({
        title: 'Copy failed',
        message: 'Unable to copy transcript to clipboard',
        color: 'red',
        autoClose: 3000,
      });
    }
  };

  return (
    <Modal
      opened={aiWorkspace.isOpen}
      onClose={closeAIWorkspace}
      size="xl"
      title={
        <Stack gap="xs" style={{ width: '100%' }}>
          <Group justify="space-between" align="center">
            <Text fw={600} size="lg">Recording Workspace</Text>
            <Badge color="green" variant="light" size="sm">
              {getStatusText(recording.transcription_status)}
            </Badge>
          </Group>
          <Group justify="space-between" align="center">
            <Text fw={500} size="md" style={{ flex: 1 }}>
              {recording.title || recording.original_filename}
            </Text>
            <Text size="sm" c="dimmed">
              {formatDuration(recording.duration || 0)} • {recording.recorded_timestamp ? new Date(recording.recorded_timestamp).toLocaleDateString() : 'Unknown'}
            </Text>
          </Group>
          {recordingTags.length > 0 && (
            <Group gap="xs">
              {recordingTags.map(tag => (
                <TagBadge key={tag.id} tag={tag} size="xs" />
              ))}
            </Group>
          )}
        </Stack>
      }
      styles={{
        body: {
          height: '80vh',
          maxHeight: '80vh',
          overflow: 'hidden', // Prevent modal body from scrolling
          padding: 0,
        },
        content: {
          height: '90vh',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      <div style={{ height: '100%', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {/* Top Half - Transcript Preview (Fixed Height) */}
        <div style={{ height: '400px', flexShrink: 0 }}>
          <Card withBorder radius="md" h="100%">
            <Stack gap="sm" h="100%">
              <Group justify="space-between" style={{ flexShrink: 0 }}>
                <Group gap="xs">
                  <LuFileText size={20} />
                  <Text fw={600} size="md">Transcript Preview</Text>
                </Group>
                <Group gap="xs">
                  <Button 
                    size="xs" 
                    variant="light" 
                    leftSection={<LuCopy size={14} />}
                    onClick={handleCopyTranscript}
                    disabled={!transcription || transcriptionLoading}
                  >
                    Copy
                  </Button>
                  <Button size="xs" variant="light" leftSection={<LuEye size={14} />}>
                    View Full
                  </Button>
                </Group>
              </Group>
              
              {/* Scrollable Transcript Area */}
              <div style={{ 
                flex: 1,
                overflow: 'auto',
                padding: '0.75rem',
                backgroundColor: 'var(--mantine-color-gray-0)',
                borderRadius: '6px',
                fontSize: '0.875rem',
                lineHeight: 1.6,
                border: '1px solid var(--mantine-color-gray-3)',
                minHeight: 0, // Allow flex shrinking
              }}>
                {transcriptionLoading ? (
                  <Center p="md">
                    <Loader size="sm" />
                  </Center>
                ) : transcription?.diarized_transcript ? (
                  <div
                    dangerouslySetInnerHTML={{
                      __html: transcription.diarized_transcript
                        .split('\n')
                        .map(line => {
                          // Parse speaker lines (format: "Speaker Name: text")
                          const speakerMatch = line.match(/^([^:]+):\s*(.*)$/);
                          if (speakerMatch) {
                            return `<div style="margin-bottom: 1rem;"><strong style="color: var(--mantine-color-blue-6);">${speakerMatch[1]}:</strong><br/>${speakerMatch[2]}</div>`;
                          }
                          return `<div style="margin-bottom: 0.5rem;">${line}</div>`;
                        })
                        .join('')
                    }}
                  />
                ) : transcription?.text ? (
                  <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                    {transcription.text}
                  </Text>
                ) : (
                  <Text size="sm" c="dimmed" ta="center">
                    No transcript available for this recording
                  </Text>
                )}
              </div>
            </Stack>
          </Card>
        </div>

        {/* Bottom Half - AI Tools & Results (Uses remaining space) */}
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {/* Quick Analysis Tools */}
            <Stack gap="sm">
              <Group gap="xs">
                <LuRocket size={20} />
                <Text fw={600} size="md">Analysis Tools</Text>
              </Group>
              <Grid>
                <Grid.Col span={6}>
                  <AIToolButton
                    icon={<LuFileText size={24} />}
                    title="Generate Summary"
                    description="Create a concise overview of the main topics and key points"
                    onComplete={() => handleToolComplete('summary', 'Summary', 
                      'This podcast episode explores relationship dynamics, focusing on the pattern of over-functioning in marriages. The main discussion centers around Kathy\'s 10-year experience in a marriage where she takes on excessive responsibility, and her desire to create a more equal partnership.'
                    )}
                  />
                </Grid.Col>
                <Grid.Col span={6}>
                  <AIToolButton
                    icon={<LuTag size={24} />}
                    title="Extract Keywords"
                    description="Identify important keywords, topics, and themes"
                    onComplete={() => handleToolComplete('keywords', 'Keywords & Topics',
                      'Primary Keywords: marriage, over-functioning, partnership, communication, boundaries, resentment, therapy, relationships\n\nKey Themes: Relationship dynamics, Personal responsibility, Equal partnership, Emotional needs, Conflict resolution'
                    )}
                  />
                </Grid.Col>
                <Grid.Col span={6}>
                  <AIToolButton
                    icon={<LuCircleHelp size={24} />}
                    title="Create Q&A"
                    description="Generate relevant questions and answers for study material"
                    onComplete={() => handleToolComplete('qa', 'Questions & Answers',
                      'Q: What is over-functioning in marriage?\nA: It\'s when one partner takes on excessive responsibility for tasks and decisions that should be shared equally in the relationship.\n\nQ: How can someone break the cycle of over-functioning?\nA: By setting clear boundaries, communicating needs effectively, and working toward equal responsibility sharing with their partner.'
                    )}
                  />
                </Grid.Col>
                <Grid.Col span={6}>
                  <AIToolButton
                    icon={<LuSmile size={24} />}
                    title="Sentiment Analysis"
                    description="Analyze emotional tone and sentiment patterns"
                    onComplete={() => handleToolComplete('sentiment', 'Sentiment Analysis',
                      'Overall Sentiment: Neutral to Positive\n\nEmotional Journey:\n• Initial frustration and concern (0-10 min)\n• Growing understanding and hope (10-30 min)\n• Determination and optimism (30-50 min)\n\nKey Emotions: Frustration (25%), Hope (35%), Determination (40%)'
                    )}
                  />
                </Grid.Col>
              </Grid>
            </Stack>

            <Divider />

            {/* Advanced Analysis */}
            <Stack gap="sm">
              <Group gap="xs">
                <LuChartBar size={20} />
                <Text fw={600} size="md">Advanced Analysis</Text>
              </Group>
              <Grid>
                <Grid.Col span={6}>
                  <AIToolButton
                    icon={<LuSearch size={24} />}
                    title="Topic Detection"
                    description="Automatically identify and categorize discussion topics"
                    onComplete={() => handleToolComplete('topics', 'Topic Detection',
                      'Topic Distribution:\n• Relationship Dynamics (45%)\n• Communication Patterns (25%)\n• Personal Boundaries (20%)\n• Conflict Resolution (10%)\n\nDiscussion Flow: Problem identification → Pattern analysis → Solution strategies → Action planning'
                    )}
                  />
                </Grid.Col>
                <Grid.Col span={6}>
                  <AIToolButton
                    icon={<LuListTodo size={24} />}
                    title="Action Items"
                    description="Extract actionable tasks and follow-up items"
                    onComplete={() => handleToolComplete('actions', 'Action Items',
                      'Immediate Actions:\n1. Practice equal responsibility sharing in daily tasks\n2. Set clear communication boundaries with partner\n3. Schedule weekly relationship check-ins\n\nLong-term Goals:\n• Develop healthier communication patterns\n• Build mutual respect and understanding\n• Create sustainable relationship dynamics'
                    )}
                  />
                </Grid.Col>
              </Grid>
            </Stack>

            {/* Results Section */}
            {results.length > 0 && (
              <>
                <Divider />
                <Stack gap="sm">
                  <Group gap="xs">
                    <LuList size={20} />
                    <Text fw={600} size="md">Generated Analysis</Text>
                  </Group>
                  <Stack gap="md">
                    {results.map((result) => (
                      <AIResult
                        key={result.id}
                        title={result.title}
                        content={result.content}
                        onRemove={() => handleRemoveResult(result.id)}
                      />
                    ))}
                  </Stack>
                </Stack>
              </>
            )}
        </div>
      </div>
    </Modal>
  );
}