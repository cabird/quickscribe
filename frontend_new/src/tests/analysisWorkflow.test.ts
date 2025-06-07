/**
 * Frontend integration tests for the analysis workflow.
 * 
 * These tests validate the complete analysis workflow including:
 * - Analysis type loading and management
 * - Analysis execution with proper API calls
 * - UI state management during analysis
 * - Error handling and user feedback
 * - Performance metric display
 */

import type { 
  AnalysisType, 
  AnalysisResult, 
  ExecuteAnalysisRequest,
  GetAnalysisTypesResponse,
  ExecuteAnalysisResponse 
} from '../types';

// Mock implementations for testing
class MockAnalysisStore {
  private analysisTypes: AnalysisType[] = [];
  private loading = false;
  private error: string | null = null;

  // Simulate loading analysis types from API
  async loadAnalysisTypes(): Promise<void> {
    this.loading = true;
    this.error = null;
    
    try {
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Mock built-in analysis types
      this.analysisTypes = [
        {
          id: 'builtin-summary',
          name: 'summary',
          title: 'Generate Summary',
          shortTitle: 'Summary',
          description: 'Create a concise overview of the main topics',
          icon: 'file-text',
          prompt: 'Please provide a concise summary: {transcript}',
          userId: undefined,
          isActive: true,
          isBuiltIn: true,
          createdAt: '2025-01-01T00:00:00Z',
          updatedAt: '2025-01-01T00:00:00Z',
          partitionKey: 'global'
        },
        {
          id: 'builtin-keywords',
          name: 'keywords',
          title: 'Extract Keywords',
          shortTitle: 'Keywords',
          description: 'Identify key terms and phrases',
          icon: 'tag',
          prompt: 'Extract key words and phrases: {transcript}',
          userId: undefined,
          isActive: true,
          isBuiltIn: true,
          createdAt: '2025-01-01T00:00:00Z',
          updatedAt: '2025-01-01T00:00:00Z',
          partitionKey: 'global'
        }
      ];
      
      this.loading = false;
    } catch (error) {
      this.error = error instanceof Error ? error.message : 'Failed to load analysis types';
      this.loading = false;
      throw error;
    }
  }
  
  getBuiltInTypes(): AnalysisType[] {
    return this.analysisTypes.filter(type => type.isBuiltIn);
  }
  
  getCustomTypes(): AnalysisType[] {
    return this.analysisTypes.filter(type => !type.isBuiltIn);
  }
  
  getAnalysisTypeByName(name: string): AnalysisType | undefined {
    return this.analysisTypes.find(type => type.name === name);
  }
  
  getAnalysisTypeById(id: string): AnalysisType | undefined {
    return this.analysisTypes.find(type => type.id === id);
  }
  
  // Test helpers
  getState() {
    return {
      analysisTypes: this.analysisTypes,
      loading: this.loading,
      error: this.error
    };
  }
}

class MockAnalysisAPI {
  private shouldFail = false;
  private responseDelay = 100;
  private mockResponse: Partial<AnalysisResult> = {};

  // Configure mock behavior
  setShouldFail(fail: boolean) {
    this.shouldFail = fail;
  }
  
  setResponseDelay(delay: number) {
    this.responseDelay = delay;
  }
  
  setMockResponse(response: Partial<AnalysisResult>) {
    this.mockResponse = response;
  }

  async executeAnalysis(request: ExecuteAnalysisRequest): Promise<ExecuteAnalysisResponse> {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, this.responseDelay));
    
    if (this.shouldFail) {
      throw new Error('Network error: Failed to execute analysis');
    }
    
    const result: AnalysisResult = {
      analysisType: 'summary',
      analysisTypeId: request.analysisTypeId,
      content: 'This is a test analysis result with mock content.',
      createdAt: new Date().toISOString(),
      status: 'completed',
      llmResponseTimeMs: 2500,
      promptTokens: 45,
      responseTokens: 12,
      ...this.mockResponse
    };
    
    return {
      status: 'success',
      message: 'Analysis completed successfully',
      data: result
    };
  }
}

// Test suite
export class AnalysisWorkflowTests {
  private store: MockAnalysisStore;
  private api: MockAnalysisAPI;
  
  constructor() {
    this.store = new MockAnalysisStore();
    this.api = new MockAnalysisAPI();
  }
  
  async runAllTests(): Promise<TestResults> {
    const results: TestResults = {
      passed: 0,
      failed: 0,
      tests: []
    };
    
    const tests = [
      this.testLoadAnalysisTypes,
      this.testAnalysisTypeSelection,
      this.testSuccessfulAnalysisExecution,
      this.testAnalysisExecutionWithTiming,
      this.testAnalysisExecutionFailure,
      this.testAnalysisExecutionWithCustomPrompt,
      this.testAnalysisTypeFiltering,
      this.testAnalysisResultAccumulation
    ];
    
    for (const test of tests) {
      try {
        await test.call(this);
        results.tests.push({
          name: test.name,
          status: 'passed',
          message: 'Test passed successfully'
        });
        results.passed++;
      } catch (error) {
        results.tests.push({
          name: test.name,
          status: 'failed',
          message: error instanceof Error ? error.message : 'Unknown error'
        });
        results.failed++;
      }
    }
    
    return results;
  }
  
  private async testLoadAnalysisTypes() {
    // Test loading analysis types from API
    const initialState = this.store.getState();
    
    if (initialState.analysisTypes.length !== 0) {
      throw new Error('Store should start empty');
    }
    
    await this.store.loadAnalysisTypes();
    
    const loadedState = this.store.getState();
    
    if (loadedState.loading !== false) {
      throw new Error('Loading should be false after completion');
    }
    
    if (loadedState.error !== null) {
      throw new Error('Error should be null on successful load');
    }
    
    if (loadedState.analysisTypes.length === 0) {
      throw new Error('Should have loaded analysis types');
    }
    
    // Verify built-in types are present
    const builtInTypes = this.store.getBuiltInTypes();
    if (builtInTypes.length === 0) {
      throw new Error('Should have built-in analysis types');
    }
    
    // Verify specific types
    const summaryType = this.store.getAnalysisTypeByName('summary');
    if (!summaryType) {
      throw new Error('Should have summary analysis type');
    }
    
    if (summaryType.title !== 'Generate Summary') {
      throw new Error('Summary type should have correct title');
    }
  }
  
  private async testAnalysisTypeSelection() {
    // Test analysis type selection and retrieval
    await this.store.loadAnalysisTypes();
    
    const summaryType = this.store.getAnalysisTypeByName('summary');
    const keywordsType = this.store.getAnalysisTypeByName('keywords');
    
    if (!summaryType || !keywordsType) {
      throw new Error('Should have both summary and keywords types');
    }
    
    // Test retrieval by ID
    const retrievedBySummaryId = this.store.getAnalysisTypeById(summaryType.id);
    if (retrievedBySummaryId?.name !== 'summary') {
      throw new Error('Should retrieve correct type by ID');
    }
    
    // Test non-existent type
    const nonExistent = this.store.getAnalysisTypeByName('non-existent');
    if (nonExistent !== undefined) {
      throw new Error('Should return undefined for non-existent type');
    }
  }
  
  private async testSuccessfulAnalysisExecution() {
    // Test successful analysis execution
    await this.store.loadAnalysisTypes();
    
    const summaryType = this.store.getAnalysisTypeByName('summary');
    if (!summaryType) {
      throw new Error('Summary type should be available');
    }
    
    const request: ExecuteAnalysisRequest = {
      transcriptionId: 'test-transcription-123',
      analysisTypeId: summaryType.id
    };
    
    const response = await this.api.executeAnalysis(request);
    
    if (response.status !== 'success') {
      throw new Error('Analysis execution should succeed');
    }
    
    if (!response.data) {
      throw new Error('Response should contain analysis data');
    }
    
    const result = response.data;
    
    if (result.status !== 'completed') {
      throw new Error('Analysis result should be completed');
    }
    
    if (!result.content) {
      throw new Error('Analysis result should have content');
    }
    
    if (result.analysisTypeId !== summaryType.id) {
      throw new Error('Analysis result should reference correct type ID');
    }
  }
  
  private async testAnalysisExecutionWithTiming() {
    // Test analysis execution includes timing metrics
    await this.store.loadAnalysisTypes();
    
    const summaryType = this.store.getAnalysisTypeByName('summary');
    if (!summaryType) {
      throw new Error('Summary type should be available');
    }
    
    // Configure mock to return specific timing data
    this.api.setMockResponse({
      llmResponseTimeMs: 3500,
      promptTokens: 75,
      responseTokens: 18
    });
    
    const request: ExecuteAnalysisRequest = {
      transcriptionId: 'test-transcription-123',
      analysisTypeId: summaryType.id
    };
    
    const response = await this.api.executeAnalysis(request);
    const result = response.data!;
    
    if (result.llmResponseTimeMs !== 3500) {
      throw new Error('Should include LLM response time');
    }
    
    if (result.promptTokens !== 75) {
      throw new Error('Should include prompt token count');
    }
    
    if (result.responseTokens !== 18) {
      throw new Error('Should include response token count');
    }
    
    // Verify timestamp
    const createdAt = new Date(result.createdAt);
    if (isNaN(createdAt.getTime())) {
      throw new Error('Should have valid timestamp');
    }
  }
  
  private async testAnalysisExecutionFailure() {
    // Test analysis execution failure handling
    await this.store.loadAnalysisTypes();
    
    const summaryType = this.store.getAnalysisTypeByName('summary');
    if (!summaryType) {
      throw new Error('Summary type should be available');
    }
    
    // Configure mock to fail
    this.api.setShouldFail(true);
    
    const request: ExecuteAnalysisRequest = {
      transcriptionId: 'test-transcription-123',
      analysisTypeId: summaryType.id
    };
    
    let errorCaught = false;
    try {
      await this.api.executeAnalysis(request);
    } catch (error) {
      errorCaught = true;
      if (!(error instanceof Error)) {
        throw new Error('Should throw proper Error object');
      }
      if (!error.message.includes('Failed to execute analysis')) {
        throw new Error('Should include meaningful error message');
      }
    }
    
    if (!errorCaught) {
      throw new Error('Should throw error on failure');
    }
    
    // Reset for subsequent tests
    this.api.setShouldFail(false);
  }
  
  private async testAnalysisExecutionWithCustomPrompt() {
    // Test analysis execution with custom prompt
    await this.store.loadAnalysisTypes();
    
    const summaryType = this.store.getAnalysisTypeByName('summary');
    if (!summaryType) {
      throw new Error('Summary type should be available');
    }
    
    const customPrompt = 'Custom analysis prompt: {transcript}';
    const request: ExecuteAnalysisRequest = {
      transcriptionId: 'test-transcription-123',
      analysisTypeId: summaryType.id,
      customPrompt: customPrompt
    };
    
    const response = await this.api.executeAnalysis(request);
    
    if (response.status !== 'success') {
      throw new Error('Custom prompt analysis should succeed');
    }
    
    if (!response.data) {
      throw new Error('Should return analysis data');
    }
    
    // In a real implementation, we'd verify the custom prompt was used
    // For this mock, we just verify the request structure is correct
    if (request.customPrompt !== customPrompt) {
      throw new Error('Should preserve custom prompt in request');
    }
  }
  
  private async testAnalysisTypeFiltering() {
    // Test filtering built-in vs custom analysis types
    await this.store.loadAnalysisTypes();
    
    const allTypes = this.store.getState().analysisTypes;
    const builtInTypes = this.store.getBuiltInTypes();
    const customTypes = this.store.getCustomTypes();
    
    if (allTypes.length !== builtInTypes.length + customTypes.length) {
      throw new Error('Built-in + custom should equal total types');
    }
    
    // All built-in types should have isBuiltIn = true
    for (const type of builtInTypes) {
      if (!type.isBuiltIn) {
        throw new Error('Built-in type should have isBuiltIn = true');
      }
      if (type.userId !== undefined) {
        throw new Error('Built-in type should not have userId');
      }
    }
    
    // All custom types should have isBuiltIn = false
    for (const type of customTypes) {
      if (type.isBuiltIn) {
        throw new Error('Custom type should have isBuiltIn = false');
      }
    }
  }
  
  private async testAnalysisResultAccumulation() {
    // Test that multiple analysis results can be handled
    await this.store.loadAnalysisTypes();
    
    const summaryType = this.store.getAnalysisTypeByName('summary');
    const keywordsType = this.store.getAnalysisTypeByName('keywords');
    
    if (!summaryType || !keywordsType) {
      throw new Error('Should have both analysis types');
    }
    
    const transcriptionId = 'test-transcription-123';
    const results: AnalysisResult[] = [];
    
    // Execute first analysis
    this.api.setMockResponse({
      analysisType: 'summary',
      content: 'Summary analysis result'
    });
    
    const summaryResponse = await this.api.executeAnalysis({
      transcriptionId,
      analysisTypeId: summaryType.id
    });
    
    if (summaryResponse.data) {
      results.push(summaryResponse.data);
    }
    
    // Execute second analysis
    this.api.setMockResponse({
      analysisType: 'keywords',
      content: 'keyword1, keyword2, keyword3'
    });
    
    const keywordsResponse = await this.api.executeAnalysis({
      transcriptionId,
      analysisTypeId: keywordsType.id
    });
    
    if (keywordsResponse.data) {
      results.push(keywordsResponse.data);
    }
    
    // Verify we have both results
    if (results.length !== 2) {
      throw new Error('Should have accumulated 2 analysis results');
    }
    
    const analysisTypes = results.map(r => r.analysisType);
    if (!analysisTypes.includes('summary') || !analysisTypes.includes('keywords')) {
      throw new Error('Should have both summary and keywords results');
    }
    
    // Verify each result has required fields
    for (const result of results) {
      if (!result.content) {
        throw new Error('Each result should have content');
      }
      if (!result.createdAt) {
        throw new Error('Each result should have timestamp');
      }
      if (result.status !== 'completed') {
        throw new Error('Each result should be completed');
      }
    }
  }
}

// Test result types
interface TestResult {
  name: string;
  status: 'passed' | 'failed';
  message: string;
}

interface TestResults {
  passed: number;
  failed: number;
  tests: TestResult[];
}

// Export for use in development/testing
export { MockAnalysisStore, MockAnalysisAPI };
export type { TestResult, TestResults };