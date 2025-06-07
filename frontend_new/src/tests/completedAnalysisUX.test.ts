import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ToolsTab } from '../components/AIWorkspace/ToolsTab';
import type { AnalysisResult, AnalysisType } from '../types';

// Mock the analysis store
vi.mock('../stores/useAnalysisStore', () => ({
  useAnalysisStore: () => ({
    analysisTypes: mockAnalysisTypes,
    loading: false,
    error: null,
  }),
}));

// Mock the icon renderer
vi.mock('../components/IconRenderer', () => ({
  IconRenderer: ({ iconName }: { iconName: string }) => <span>Icon-{iconName}</span>,
}));

const mockAnalysisTypes: AnalysisType[] = [
  {
    id: 'summary-type-id',
    name: 'summary',
    title: 'Generate Summary',
    shortTitle: 'Summary',
    description: 'Create a comprehensive summary',
    icon: 'file-text',
    prompt: 'Summarize this transcript: {transcript}',
    userId: null,
    isActive: true,
    isBuiltIn: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
    partitionKey: 'global',
  },
  {
    id: 'qa-type-id',
    name: 'qa',
    title: 'Generate Q&A',
    shortTitle: 'Q&A',
    description: 'Generate questions and answers',
    icon: 'circle-help',
    prompt: 'Generate Q&A for: {transcript}',
    userId: null,
    isActive: true,
    isBuiltIn: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
    partitionKey: 'global',
  },
];

const mockCompletedResults: AnalysisResult[] = [
  {
    analysisType: 'summary',
    analysisTypeId: 'summary-type-id',
    content: 'This is a summary...',
    createdAt: '2024-01-01T00:00:00Z',
    status: 'completed',
  },
];

const mockPendingResults: AnalysisResult[] = [
  {
    analysisType: 'qa',
    analysisTypeId: 'qa-type-id',
    content: '',
    createdAt: '2024-01-01T00:00:00Z',
    status: 'pending',
  },
];

describe('Completed Analysis UX Enhancement', () => {
  const mockOnRunAnalysis = vi.fn();
  const mockOnViewResult = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows overlay with View/Rerun buttons on hover for completed analysis', async () => {
    render(
      <ToolsTab
        analysisResults={mockCompletedResults}
        onRunAnalysis={mockOnRunAnalysis}
        onViewResult={mockOnViewResult}
      />
    );

    // Find the completed analysis tool
    const summaryTool = screen.getByText('Generate Summary').closest('[data-testid], div');
    expect(summaryTool).toBeTruthy();

    // Hover over the completed tool
    fireEvent.mouseEnter(summaryTool!);

    // Wait for overlay to appear
    await waitFor(() => {
      expect(screen.getByText('Analysis Complete')).toBeInTheDocument();
      expect(screen.getByText('View')).toBeInTheDocument();
      expect(screen.getByText('Rerun')).toBeInTheDocument();
    });
  });

  it('calls onViewResult when View button is clicked', async () => {
    render(
      <ToolsTab
        analysisResults={mockCompletedResults}
        onRunAnalysis={mockOnRunAnalysis}
        onViewResult={mockOnViewResult}
      />
    );

    const summaryTool = screen.getByText('Generate Summary').closest('div')!;
    fireEvent.mouseEnter(summaryTool);

    await waitFor(() => {
      expect(screen.getByText('View')).toBeInTheDocument();
    });

    const viewButton = screen.getByText('View');
    fireEvent.click(viewButton);

    expect(mockOnViewResult).toHaveBeenCalledWith('summary');
    expect(mockOnRunAnalysis).not.toHaveBeenCalled();
  });

  it('calls onRunAnalysis when Rerun button is clicked', async () => {
    render(
      <ToolsTab
        analysisResults={mockCompletedResults}
        onRunAnalysis={mockOnRunAnalysis}
        onViewResult={mockOnViewResult}
      />
    );

    const summaryTool = screen.getByText('Generate Summary').closest('div')!;
    fireEvent.mouseEnter(summaryTool);

    await waitFor(() => {
      expect(screen.getByText('Rerun')).toBeInTheDocument();
    });

    const rerunButton = screen.getByText('Rerun');
    fireEvent.click(rerunButton);

    expect(mockOnRunAnalysis).toHaveBeenCalledWith('summary');
    expect(mockOnViewResult).not.toHaveBeenCalled();
  });

  it('does not show overlay for non-completed analysis', () => {
    render(
      <ToolsTab
        analysisResults={mockPendingResults}
        onRunAnalysis={mockOnRunAnalysis}
        onViewResult={mockOnViewResult}
      />
    );

    const qaTool = screen.getByText('Running...').closest('div')!;
    fireEvent.mouseEnter(qaTool);

    // Overlay should not appear for running analysis
    expect(screen.queryByText('Analysis Complete')).not.toBeInTheDocument();
    expect(screen.queryByText('View')).not.toBeInTheDocument();
    expect(screen.queryByText('Rerun')).not.toBeInTheDocument();
  });

  it('directly runs analysis for non-completed tools', () => {
    render(
      <ToolsTab
        analysisResults={[]} // No completed results
        onRunAnalysis={mockOnRunAnalysis}
        onViewResult={mockOnViewResult}
      />
    );

    const summaryTool = screen.getByText('Generate Summary').closest('div')!;
    fireEvent.click(summaryTool);

    expect(mockOnRunAnalysis).toHaveBeenCalledWith('summary');
  });

  it('hides overlay when mouse leaves the tool', async () => {
    render(
      <ToolsTab
        analysisResults={mockCompletedResults}
        onRunAnalysis={mockOnRunAnalysis}
        onViewResult={mockOnViewResult}
      />
    );

    const summaryTool = screen.getByText('Generate Summary').closest('div')!;
    
    // Show overlay
    fireEvent.mouseEnter(summaryTool);
    await waitFor(() => {
      expect(screen.getByText('Analysis Complete')).toBeInTheDocument();
    });

    // Hide overlay
    fireEvent.mouseLeave(summaryTool);
    await waitFor(() => {
      expect(screen.queryByText('Analysis Complete')).not.toBeInTheDocument();
    });
  });
});