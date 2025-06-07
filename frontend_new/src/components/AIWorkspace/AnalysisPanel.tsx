import { useState } from 'react';
import { Box } from '@mantine/core';
import { TabNavigation, type TabType } from './TabNavigation';
import { ToolsTab } from './ToolsTab';
import { ResultsOverviewTab } from './ResultsOverviewTab';
import { ResultTab } from './ResultTab';
import type { AnalysisResult } from '../../types';

interface AnalysisPanelProps {
  analysisResults: AnalysisResult[];
  onRunAnalysis: (analysisType: AnalysisResult['analysisType']) => void;
  onDeleteAnalysis?: (analysisType: AnalysisResult['analysisType']) => void;
  height: number;
}

export function AnalysisPanel({ 
  analysisResults, 
  onRunAnalysis, 
  onDeleteAnalysis,
  height 
}: AnalysisPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('tools');

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
  };

  const handleSelectResult = (analysisType: AnalysisResult['analysisType']) => {
    setActiveTab(analysisType);
  };

  const handleRunAnalysis = (analysisType: AnalysisResult['analysisType']) => {
    onRunAnalysis(analysisType);
    // Stay on current tab so user can see button state change
  };

  const getActiveAnalysisResult = (): AnalysisResult | undefined => {
    if (activeTab === 'tools' || activeTab === 'results') return undefined;
    return analysisResults.find(result => result.analysisType === activeTab);
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'tools':
        return (
          <ToolsTab 
            analysisResults={analysisResults}
            onRunAnalysis={handleRunAnalysis}
          />
        );
      
      case 'results':
        return (
          <ResultsOverviewTab 
            analysisResults={analysisResults}
            onSelectResult={handleSelectResult}
          />
        );
      
      default:
        const result = getActiveAnalysisResult();
        if (!result) {
          // This shouldn't happen, but fallback to tools tab
          setActiveTab('tools');
          return null;
        }
        return (
          <ResultTab 
            analysisResult={result}
            onRerun={handleRunAnalysis}
            onDelete={onDeleteAnalysis}
          />
        );
    }
  };

  return (
    <Box
      data-resizable-panel
      style={{
        height: `${height}px`,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'white',
        borderTop: '1px solid var(--mantine-color-gray-3)',
        position: 'relative',
      }}
    >
      {/* Tab Navigation */}
      <TabNavigation 
        activeTab={activeTab}
        analysisResults={analysisResults}
        onTabChange={handleTabChange}
      />
      
      {/* Tab Content */}
      <Box
        style={{
          flex: 1,
          overflow: 'auto',
          minHeight: 0,
        }}
      >
        {renderTabContent()}
      </Box>
    </Box>
  );
}