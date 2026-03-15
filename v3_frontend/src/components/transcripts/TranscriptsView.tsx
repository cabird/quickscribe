import { useState, useMemo, useCallback, useEffect } from 'react';
import { makeStyles, Button } from '@fluentui/react-components';
import { ArrowLeft20Regular } from '@fluentui/react-icons';
import { TopActionBar } from '../layout/TopActionBar';
import { RecordingsList } from './RecordingsList';
import { TranscriptViewer } from './TranscriptViewer';
import { ResizableSplitter } from '../layout/ResizableSplitter';
import { useRecordings } from '../../hooks/useRecordings';
import { useTranscription } from '../../hooks/useTranscription';
import { exportTranscriptToFile } from '../../utils/exportTranscript';
import { showToast } from '../../utils/toast';
import { useIsMobile } from '../../hooks/useIsMobile';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    minHeight: 0,
  },
  viewContainer: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
    minHeight: 0,
  },
  mobileBackBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    borderBottom: '1px solid #e0e0e0',
    flexShrink: 0,
  },
  mobileBackTitle: {
    fontSize: '14px',
    fontWeight: 600,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    flex: 1,
  },
  mobileFullWidth: {
    width: '100%',
    flex: 1,
  },
});

interface TranscriptsViewProps {
  /** External recording ID to navigate to (e.g., from People view) */
  navigateToRecordingId?: string | null;
  /** Callback when navigation is complete */
  onNavigationComplete?: () => void;
}

export function TranscriptsView({ navigateToRecordingId, onNavigationComplete }: TranscriptsViewProps = {}) {
  const styles = useStyles();
  const isMobile = useIsMobile();
  const [selectedRecordingId, setSelectedRecordingId] = useState<string | null>(null);
  const [checkedRecordingIds, setCheckedRecordingIds] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [searchType, setSearchType] = useState<'basic' | 'fulltext'>('basic');
  const [dateRange, setDateRange] = useState<'all' | 'week' | 'month' | 'quarter'>('all');
  const [listPanelWidth, setListPanelWidth] = useState(35); // percentage

  const { recordings, loading: recordingsLoading, refetch } = useRecordings();

  // Calculate total token count for selected recordings
  const selectedTokenCount = useMemo(() => {
    return Array.from(checkedRecordingIds).reduce((total, id) => {
      const recording = recordings.find(r => r.id === id);
      return total + (recording?.token_count || 0);
    }, 0);
  }, [checkedRecordingIds, recordings]);

  // Handle check/uncheck of recordings
  const handleCheckChange = useCallback((recordingId: string, checked: boolean) => {
    setCheckedRecordingIds(prev => {
      const next = new Set(prev);
      if (checked) {
        next.add(recordingId);
      } else {
        next.delete(recordingId);
      }
      return next;
    });
  }, []);

  // Clear all selections
  const handleClearSelection = useCallback(() => {
    setCheckedRecordingIds(new Set());
  }, []);

  // Handle chat with selected transcripts
  const handleChatWithSelected = useCallback(() => {
    // TODO: Implement chat drawer opening with selected transcripts
    console.log('Chat with selected:', Array.from(checkedRecordingIds));
  }, [checkedRecordingIds]);
  const selectedRecording = recordings.find(r => r.id === selectedRecordingId);
  const { transcription, loading: transcriptionLoading } = useTranscription(
    selectedRecording?.transcription_id || null
  );

  // Search/Filter Logic
  const filteredRecordings = useMemo(() => {
    let filtered = recordings;

    // Search filter
    if (searchQuery) {
      filtered = filtered.filter(r => {
        if (searchType === 'basic') {
          return (
            r.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            r.description?.toLowerCase().includes(searchQuery.toLowerCase())
          );
        }
        // Full-text search requires transcription - defer to backend in Phase 2
        return true;
      });
    }

    // Date range filter
    if (dateRange !== 'all') {
      const now = new Date();
      const cutoff = new Date();

      switch (dateRange) {
        case 'week':
          cutoff.setDate(now.getDate() - 7);
          break;
        case 'month':
          cutoff.setMonth(now.getMonth() - 1);
          break;
        case 'quarter':
          cutoff.setMonth(now.getMonth() - 3);
          break;
      }

      filtered = filtered.filter(r =>
        new Date(r.upload_timestamp || '') >= cutoff
      );
    }

    return filtered;
  }, [recordings, searchQuery, searchType, dateRange]);

  const handleExport = () => {
    if (selectedRecording && transcription) {
      try {
        exportTranscriptToFile(selectedRecording, transcription);
        showToast.exportSuccess();
      } catch (error) {
        showToast.apiError(error);
      }
    } else {
      showToast.warning('Please select a recording with a transcript to export');
    }
  };

  const handleResize = useCallback((delta: number) => {
    setListPanelWidth(prev => {
      // Get the container width to calculate percentage
      const containerWidth = window.innerWidth - 68; // Subtract nav rail width
      const deltaPercent = (delta / containerWidth) * 100;
      const newWidth = prev + deltaPercent;
      // Constrain between 20% and 60%
      return Math.max(20, Math.min(60, newWidth));
    });
  }, []);

  // Handle external navigation to a specific recording
  useEffect(() => {
    if (navigateToRecordingId) {
      setSelectedRecordingId(navigateToRecordingId);
      // Notify parent that navigation is complete
      onNavigationComplete?.();
    }
  }, [navigateToRecordingId, onNavigationComplete]);

  // Listen for recording deleted event
  useEffect(() => {
    const handleRecordingDeleted = (event: CustomEvent) => {
      const { recordingId } = event.detail;
      // If the deleted recording was selected, clear selection
      if (recordingId === selectedRecordingId) {
        setSelectedRecordingId(null);
      }
      // If the deleted recording was checked, remove from checked set
      if (checkedRecordingIds.has(recordingId)) {
        setCheckedRecordingIds(prev => {
          const next = new Set(prev);
          next.delete(recordingId);
          return next;
        });
      }
      // Refetch recordings to update the list
      refetch();
    };

    window.addEventListener('recordingDeleted', handleRecordingDeleted as EventListener);
    return () => {
      window.removeEventListener('recordingDeleted', handleRecordingDeleted as EventListener);
    };
  }, [selectedRecordingId, checkedRecordingIds, refetch]);

  const handleMobileBack = useCallback(() => {
    setSelectedRecordingId(null);
  }, []);

  // Mobile: show either list or detail, not both
  if (isMobile) {
    const showDetail = selectedRecordingId !== null;

    return (
      <div className={styles.container}>
        {showDetail ? (
          <>
            <div className={styles.mobileBackBar}>
              <Button
                appearance="subtle"
                icon={<ArrowLeft20Regular />}
                onClick={handleMobileBack}
              >
                Back
              </Button>
              <span className={styles.mobileBackTitle}>
                {selectedRecording?.title || 'Transcript'}
              </span>
            </div>
            <TranscriptViewer
              transcription={transcription}
              recording={selectedRecording || null}
              loading={transcriptionLoading}
            />
          </>
        ) : (
          <>
            <TopActionBar
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              searchType={searchType}
              onSearchTypeChange={setSearchType}
              dateRange={dateRange}
              onDateRangeChange={setDateRange}
              onExport={handleExport}
              onRefresh={refetch}
              selectedCount={checkedRecordingIds.size}
              selectedTokenCount={selectedTokenCount}
              onClearSelection={handleClearSelection}
              onChatWithSelected={handleChatWithSelected}
              isMobile
            />
            <RecordingsList
              recordings={filteredRecordings}
              selectedRecordingId={selectedRecordingId}
              onRecordingSelect={setSelectedRecordingId}
              checkedRecordingIds={checkedRecordingIds}
              onCheckChange={handleCheckChange}
              loading={recordingsLoading}
              width={100}
            />
          </>
        )}
      </div>
    );
  }

  // Desktop: side-by-side list + detail
  return (
    <div className={styles.container}>
      <TopActionBar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchType={searchType}
        onSearchTypeChange={setSearchType}
        dateRange={dateRange}
        onDateRangeChange={setDateRange}
        onExport={handleExport}
        onRefresh={refetch}
        selectedCount={checkedRecordingIds.size}
        selectedTokenCount={selectedTokenCount}
        onClearSelection={handleClearSelection}
        onChatWithSelected={handleChatWithSelected}
      />
      <div className={styles.viewContainer}>
        <RecordingsList
          recordings={filteredRecordings}
          selectedRecordingId={selectedRecordingId}
          onRecordingSelect={setSelectedRecordingId}
          checkedRecordingIds={checkedRecordingIds}
          onCheckChange={handleCheckChange}
          loading={recordingsLoading}
          width={listPanelWidth}
        />
        <ResizableSplitter onResize={handleResize} />
        <TranscriptViewer
          transcription={transcription}
          recording={selectedRecording || null}
          loading={transcriptionLoading}
        />
      </div>
    </div>
  );
}
