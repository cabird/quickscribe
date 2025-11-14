// API response wrappers
export interface ApiResponse<T> {
  status: 'success' | 'error';
  data?: T;
  error?: string;
  message?: string;
}

// Pagination (for future)
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

// Search/Filter params
export interface RecordingFilters {
  searchQuery?: string;
  searchType?: 'basic' | 'fulltext';
  dateRange?: 'all' | 'week' | 'month' | 'quarter';
  tagIds?: string[];
}

// Transcription segment from parsed JSON
export interface TranscriptionSegment {
  speaker: string;
  text: string;
  start?: number;
  end?: number;
}
