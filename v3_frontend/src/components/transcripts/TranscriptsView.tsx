import { useState, useMemo } from 'react';
import { makeStyles } from '@fluentui/react-components';
import { TopActionBar } from '../layout/TopActionBar';
import { RecordingsList } from './RecordingsList';
import { TranscriptViewer } from './TranscriptViewer';
import { useRecordings } from '../../hooks/useRecordings';
import { useTranscription } from '../../hooks/useTranscription';
import { exportTranscriptToFile } from '../../utils/exportTranscript';
import { showToast } from '../../utils/toast';

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
});

export function TranscriptsView() {
  const styles = useStyles();
  const [selectedRecordingId, setSelectedRecordingId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchType, setSearchType] = useState<'basic' | 'fulltext'>('basic');
  const [dateRange, setDateRange] = useState<'all' | 'week' | 'month' | 'quarter'>('all');

  const { recordings, loading: recordingsLoading, refetch } = useRecordings();
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
      />
      <div className={styles.viewContainer}>
        <RecordingsList
          recordings={filteredRecordings}
          selectedRecordingId={selectedRecordingId}
          onRecordingSelect={setSelectedRecordingId}
          loading={recordingsLoading}
        />
        <TranscriptViewer
          transcription={transcription}
          recording={selectedRecording || null}
          loading={transcriptionLoading}
        />
      </div>
    </div>
  );
}
