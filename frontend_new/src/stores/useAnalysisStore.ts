import { create } from 'zustand';
import { getAnalysisTypes } from '../api/analysisTypes';
import type { AnalysisType } from '../types';

interface AnalysisStore {
  // State
  analysisTypes: AnalysisType[];
  loading: boolean;
  error: string | null;
  
  // Actions
  loadAnalysisTypes: () => Promise<void>;
  
  // Selectors
  getBuiltInTypes: () => AnalysisType[];
  getCustomTypes: () => AnalysisType[];
  getAnalysisTypeById: (id: string) => AnalysisType | undefined;
  getAnalysisTypeByName: (name: string) => AnalysisType | undefined;
}

export const useAnalysisStore = create<AnalysisStore>((set, get) => ({
  // Initial state
  analysisTypes: [],
  loading: false,
  error: null,
  
  // Load analysis types from backend - simple, no caching
  loadAnalysisTypes: async () => {
    set({ loading: true, error: null });
    
    try {
      const analysisTypes = await getAnalysisTypes();
      set({ analysisTypes, loading: false });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load analysis types';
      set({ error: errorMessage, loading: false });
      throw error; // Re-throw so caller can handle notification
    }
  },
  
  // Get built-in analysis types
  getBuiltInTypes: () => {
    const { analysisTypes } = get();
    return Array.isArray(analysisTypes) ? analysisTypes.filter(type => type.isBuiltIn) : [];
  },
  
  // Get user's custom analysis types
  getCustomTypes: () => {
    const { analysisTypes } = get();
    return Array.isArray(analysisTypes) ? analysisTypes.filter(type => !type.isBuiltIn) : [];
  },
  
  // Find analysis type by ID
  getAnalysisTypeById: (id: string) => {
    const { analysisTypes } = get();
    return Array.isArray(analysisTypes) ? analysisTypes.find(type => type.id === id) : undefined;
  },
  
  // Find analysis type by name (for backward compatibility)
  getAnalysisTypeByName: (name: string) => {
    const { analysisTypes } = get();
    return Array.isArray(analysisTypes) ? analysisTypes.find(type => type.name === name) : undefined;
  },
}));