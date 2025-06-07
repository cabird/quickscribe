import { Box, Group, Text, Badge } from '@mantine/core';
import type { AnalysisResult } from '../../types';
import { useAnalysisStore } from '../../stores/useAnalysisStore';

export type TabType = 'tools' | 'results' | AnalysisResult['analysisType'];

interface TabNavigationProps {
  activeTab: TabType;
  analysisResults: AnalysisResult[];
  onTabChange: (tab: TabType) => void;
}

export function TabNavigation({ activeTab, analysisResults, onTabChange }: TabNavigationProps) {
  const { getAnalysisTypeByName } = useAnalysisStore();
  const completedResults = analysisResults.filter(result => result.status === 'completed');
  const completedTypes = new Set(completedResults.map(result => result.analysisType));

  const renderTab = (tabId: TabType, label: string, hasResults?: boolean, badge?: number) => {
    const isActive = activeTab === tabId;
    
    return (
      <Box
        key={tabId}
        onClick={() => onTabChange(tabId)}
        style={{
          padding: '12px 20px',
          borderBottom: isActive ? '2px solid var(--mantine-color-blue-6)' : '2px solid transparent',
          backgroundColor: isActive ? 'white' : 'transparent',
          cursor: 'pointer',
          fontSize: '14px',
          color: isActive ? 'var(--mantine-color-blue-6)' : 'var(--mantine-color-gray-6)',
          position: 'relative',
          borderRight: '1px solid var(--mantine-color-gray-3)',
          transition: 'all 0.2s ease',
        }}
        __vars={{
          '--hover-bg': 'var(--mantine-color-gray-1)',
        }}
        sx={{
          '&:hover': {
            backgroundColor: isActive ? 'white' : 'var(--hover-bg)',
            color: isActive ? 'var(--mantine-color-blue-6)' : 'var(--mantine-color-gray-7)',
          },
          '&:last-child': {
            borderRight: 'none',
          },
        }}
      >
        <Group gap="xs" justify="center">
          <Text size="sm" fw={isActive ? 600 : 400}>
            {label}
          </Text>
          {badge !== undefined && (
            <Badge size="xs" color="blue" variant="filled">
              {badge}
            </Badge>
          )}
        </Group>
        
        {/* Results indicator dot */}
        {hasResults && (
          <Box
            style={{
              position: 'absolute',
              top: '8px',
              right: '8px',
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: 'var(--mantine-color-green-6)',
            }}
          />
        )}
      </Box>
    );
  };

  return (
    <Box
      style={{
        display: 'flex',
        borderBottom: '1px solid var(--mantine-color-gray-3)',
        backgroundColor: 'var(--mantine-color-gray-0)',
        flexShrink: 0,
        overflowX: 'auto',
      }}
    >
      {/* Always show Tools and Results tabs */}
      {renderTab('tools', 'Tools')}
      {renderTab('results', 'Results', completedResults.length > 0, completedResults.length)}
      
      {/* Dynamic tabs for completed analyses */}
      {Array.from(completedTypes).map(analysisTypeName => {
        const analysisType = getAnalysisTypeByName(analysisTypeName);
        if (!analysisType) return null;
        
        return renderTab(analysisTypeName, analysisType.shortTitle, true);
      })}
    </Box>
  );
}