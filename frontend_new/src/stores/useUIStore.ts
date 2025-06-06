import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

type SidebarTab = 'upload' | 'browse' | 'settings';

interface UIState {
  // Sidebar state
  sidebarTab: SidebarTab;
  setSidebarTab: (tab: SidebarTab) => void;
  
  // Filter state
  filters: {
    status: string;
    tags: string[];
    search: string;
  };
  setFilters: (filters: Partial<UIState['filters']>) => void;
  
  // AI Workspace state
  aiWorkspace: {
    isOpen: boolean;
    recordingId: string | null;
  };
  openAIWorkspace: (recordingId: string) => void;
  closeAIWorkspace: () => void;
  
  // View mode
  viewMode: 'grid' | 'list';
  setViewMode: (mode: 'grid' | 'list') => void;
  
  // Loading states
  uploadLoading: boolean;
  setUploadLoading: (loading: boolean) => void;
}

export const useUIStore = create<UIState>()(
  devtools(
    (set) => ({
      // Sidebar state
      sidebarTab: 'browse',
      setSidebarTab: (tab) =>
        set({ sidebarTab: tab }, false, 'setSidebarTab'),

      // Filter state
      filters: {
        status: 'all',
        tags: [],
        search: '',
      },
      setFilters: (newFilters) =>
        set(
          (state) => ({
            filters: { ...state.filters, ...newFilters },
          }),
          false,
          'setFilters'
        ),

      // AI Workspace state
      aiWorkspace: {
        isOpen: false,
        recordingId: null,
      },
      openAIWorkspace: (recordingId) =>
        set(
          {
            aiWorkspace: {
              isOpen: true,
              recordingId,
            },
          },
          false,
          'openAIWorkspace'
        ),
      closeAIWorkspace: () =>
        set(
          {
            aiWorkspace: {
              isOpen: false,
              recordingId: null,
            },
          },
          false,
          'closeAIWorkspace'
        ),

      // View mode
      viewMode: 'grid',
      setViewMode: (mode) =>
        set({ viewMode: mode }, false, 'setViewMode'),

      // Loading states
      uploadLoading: false,
      setUploadLoading: (loading) =>
        set({ uploadLoading: loading }, false, 'setUploadLoading'),
    }),
    {
      name: 'ui-store',
    }
  )
);