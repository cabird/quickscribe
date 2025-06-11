import { Modal } from '@mantine/core';
import { useUIStore } from '../../stores/useUIStore';
import { useRecordingStore } from '../../stores/useRecordingStore';
import { useTagStore } from '../../stores/useTagStore';
import { fetchTranscription } from '../../api/recordings';
import { executeAnalysis } from '../../api/analysisTypes';
import { useState, useEffect } from 'react';
import { TranscriptPanel } from './TranscriptPanel';
import { AnalysisPanel } from './AnalysisPanel';
import { ResizableHandle } from './ResizableHandle';
import { useAnalysisStore } from '../../stores/useAnalysisStore';
import { notifications } from '@mantine/notifications';
import type { Recording, Transcription, AnalysisResult } from '../../types';

export function AIWorkspaceModal() {
  const { aiWorkspace, closeAIWorkspace } = useUIStore();
  const { getRecordingById, updateRecording } = useRecordingStore();
  const { getTagsByIds } = useTagStore();
  
  const [transcription, setTranscription] = useState<Transcription | null>(null);
  const [transcriptionLoading, setTranscriptionLoading] = useState(false);
  const [analysisResults, setAnalysisResults] = useState<AnalysisResult[]>([]);
  const { getAnalysisTypeByName } = useAnalysisStore();
  const [analysisPanelHeight, setAnalysisPanelHeight] = useState(350);

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
        .then(transcription => {
          setTranscription(transcription);
          // Load existing analysis results from transcription
          setAnalysisResults(transcription.analysisResults || []);
        })
        .catch(error => {
          console.error('Failed to fetch transcription:', error);
          setTranscription(null);
          setAnalysisResults([]);
        })
        .finally(() => setTranscriptionLoading(false));
    } else {
      setTranscription(null);
      setAnalysisResults([]);
    }
  }, [recording?.transcription_id, aiWorkspace.isOpen]);

  const handleRunAnalysis = async (analysisType: AnalysisResult['analysisType']) => {
    if (!transcription?.id) {
      notifications.show({
        title: 'Error',
        message: 'No transcription available for analysis',
        color: 'red',
      });
      return;
    }

    // Get the analysis type details
    const analysisTypeDetails = getAnalysisTypeByName(analysisType);
    if (!analysisTypeDetails) {
      notifications.show({
        title: 'Error',
        message: 'Analysis type not found',
        color: 'red',
      });
      return;
    }

    // Add pending result immediately for optimistic UI
    const pendingResult: AnalysisResult = {
      analysisType,
      analysisTypeId: analysisTypeDetails.id,
      content: '',
      createdAt: new Date().toISOString(),
      status: 'pending',
    };
    
    setAnalysisResults(prev => {
      // Remove any existing result of the same type, then add the pending one
      const filtered = prev.filter(r => r.analysisType !== analysisType);
      return [...filtered, pendingResult];
    });

    try {
      // Execute the analysis
      const response = await executeAnalysis({
        transcriptionId: transcription.id,
        analysisTypeId: analysisTypeDetails.id,
      });

      // Refresh the transcription to get the updated analysis results
      const updatedTranscription = await fetchTranscription(transcription.id);
      setAnalysisResults(updatedTranscription.analysisResults || []);
      setTranscription(updatedTranscription);

      notifications.show({
        title: 'Analysis Complete',
        message: `${analysisTypeDetails.title} analysis completed successfully`,
        color: 'green',
      });

    } catch (error) {
      console.error('Analysis failed:', error);
      
      // Update the pending result to show failure
      setAnalysisResults(prev =>
        prev.map(r => r.analysisType === analysisType ? {
          ...r,
          status: 'failed' as const,
          errorMessage: 'Analysis failed. Please try again.',
        } : r)
      );

      notifications.show({
        title: 'Analysis Failed',
        message: 'There was an error running the analysis. Please try again.',
        color: 'red',
      });
    }
  };

  const handleDeleteAnalysis = (analysisType: AnalysisResult['analysisType']) => {
    setAnalysisResults(prev => prev.filter(r => r.analysisType !== analysisType));
  };

  const handleResizePanel = (newHeight: number) => {
    setAnalysisPanelHeight(newHeight);
  };

  const handleRecordingUpdate = (updatedRecording: Recording) => {
    updateRecording(updatedRecording);
  };

  const handleTranscriptReload = async () => {
    if (recording?.transcription_id) {
      setTranscriptionLoading(true);
      try {
        const updatedTranscription = await fetchTranscription(recording.transcription_id);
        setTranscription(updatedTranscription);
        setAnalysisResults(updatedTranscription.analysisResults || []);
      } catch (error) {
        console.error('Failed to reload transcription:', error);
      } finally {
        setTranscriptionLoading(false);
      }
    }
  };

  const handlePostProcessingUpdate = (updatedRecording: Recording, updatedTranscription: Transcription) => {
    // Update both recording and transcription from the post-processing response
    handleRecordingUpdate(updatedRecording);
    setTranscription(updatedTranscription);
    setAnalysisResults(updatedTranscription.analysisResults || []);
  };

  return (
    <Modal
      opened={aiWorkspace.isOpen}
      onClose={closeAIWorkspace}
      size="xl"
      title=""
      styles={{
        body: {
          height: '85vh',
          maxHeight: '85vh',
          overflow: 'hidden',
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
      <div style={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column',
        position: 'relative',
      }}>
        {/* Top Section - Transcript Panel */}
        <div style={{ 
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
        }}>
          <TranscriptPanel
            recording={recording}
            recordingTags={recordingTags}
            transcription={transcription}
            transcriptionLoading={transcriptionLoading}
            onRecordingUpdate={handleRecordingUpdate}
            onTranscriptReload={handleTranscriptReload}
            onPostProcessingUpdate={handlePostProcessingUpdate}
          />
        </div>

        {/* Bottom Section - Analysis Panel with Resizable Handle */}
        <div style={{ position: 'relative' }}>
          <ResizableHandle 
            onResize={handleResizePanel}
            minHeight={150}
            maxHeight={window.innerHeight * 0.7}
          />
          <AnalysisPanel
            analysisResults={analysisResults}
            onRunAnalysis={handleRunAnalysis}
            onDeleteAnalysis={handleDeleteAnalysis}
            height={analysisPanelHeight}
          />
        </div>
      </div>
    </Modal>
  );
}