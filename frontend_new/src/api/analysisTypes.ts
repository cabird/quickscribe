import axios from 'axios';
import type { 
  AnalysisType, 
  CreateAnalysisTypeRequest,
  UpdateAnalysisTypeRequest,
  ExecuteAnalysisRequest,
  GetAnalysisTypesResponse,
  CreateAnalysisTypeResponse,
  UpdateAnalysisTypeResponse,
  ExecuteAnalysisResponse
} from '../types';

/**
 * Fetch all analysis types available to the current user
 * Returns built-in types + user's custom types
 */
export async function getAnalysisTypes(): Promise<AnalysisType[]> {
  const response = await axios.get<GetAnalysisTypesResponse>('/api/ai/analysis-types');
  return response.data.data || [];
}

/**
 * Create a new custom analysis type
 */
export async function createAnalysisType(data: CreateAnalysisTypeRequest): Promise<AnalysisType> {
  const response = await axios.post<CreateAnalysisTypeResponse>('/api/ai/analysis-types', data);
  return response.data.data!;
}

/**
 * Update an existing analysis type (user can only edit their own)
 */
export async function updateAnalysisType(id: string, updates: UpdateAnalysisTypeRequest): Promise<AnalysisType> {
  const response = await axios.put<UpdateAnalysisTypeResponse>(`/api/ai/analysis-types/${id}`, updates);
  return response.data.data!;
}

/**
 * Delete a custom analysis type (cannot delete built-in types)
 */
export async function deleteAnalysisType(id: string): Promise<void> {
  await axios.delete(`/api/ai/analysis-types/${id}`);
}

/**
 * Execute analysis with dynamic type and prompt
 */
export async function executeAnalysis(data: ExecuteAnalysisRequest): Promise<void> {
  await axios.post<ExecuteAnalysisResponse>('/api/ai/execute-analysis', data);
}