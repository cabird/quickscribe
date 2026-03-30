import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import * as api from "./api";
import type {
  RecordingFilters,
  SyncRunFilters,
  UpdateRecordingRequest,
  PasteTranscriptRequest,
  AssignSpeakerRequest,
  CreateParticipantRequest,
  UpdateParticipantRequest,
  CreateTagRequest,
  UpdateTagRequest,
  ChatRequest,
  AnalysisRequest,
  UpdateSettingsRequest,
  CreateAnalysisTemplateRequest,
  UpdateAnalysisTemplateRequest,
  PaginatedResponse,
  RecordingSummary,
  RecordingDetail,
  Participant,
  ParticipantWithRecordings,
  Tag,
  SyncRunSummary,
  SyncRunDetail,
  UserProfile,
  AnalysisTemplate,
  ChatResponse,
  AnalysisResponse,
  Collection,
  CollectionDetail,
  CollectionSearchRecord,
  SearchHistoryItem,
} from "@/types/models";

// =============================================================================
// Query key factories
// =============================================================================

export const queryKeys = {
  recordings: {
    all: ["recordings"] as const,
    list: (filters: RecordingFilters) => ["recordings", "list", filters] as const,
    detail: (id: string) => ["recordings", "detail", id] as const,
    search: (query: string) => ["recordings", "search", query] as const,
  },
  participants: {
    all: ["participants"] as const,
    list: () => ["participants", "list"] as const,
    detail: (id: string) => ["participants", "detail", id] as const,
  },
  tags: {
    all: ["tags"] as const,
    list: () => ["tags", "list"] as const,
  },
  syncRuns: {
    all: ["syncRuns"] as const,
    list: (filters: SyncRunFilters) => ["syncRuns", "list", filters] as const,
    detail: (id: string) => ["syncRuns", "detail", id] as const,
  },
  user: {
    current: ["user", "current"] as const,
  },
  analysisTemplates: {
    all: ["analysisTemplates"] as const,
    list: () => ["analysisTemplates", "list"] as const,
  },
  version: {
    current: ["version"] as const,
  },
  collections: {
    all: ["collections"] as const,
    list: () => ["collections", "list"] as const,
    detail: (id: string) => ["collections", "detail", id] as const,
    searches: (id: string) => ["collections", "searches", id] as const,
  },
  searchHistory: {
    all: ["searchHistory"] as const,
    list: () => ["searchHistory", "list"] as const,
  },
} as const;

// =============================================================================
// Query hooks
// =============================================================================

// -- Recordings -------------------------------------------------------------

export function useRecordings(
  filters: RecordingFilters = {},
  options?: Partial<UseQueryOptions<PaginatedResponse<RecordingSummary>>>,
) {
  return useQuery({
    queryKey: queryKeys.recordings.list(filters),
    queryFn: () => api.fetchRecordings(filters),
    ...options,
  });
}

export function useRecording(
  id: string,
  options?: Partial<UseQueryOptions<RecordingDetail>>,
) {
  return useQuery({
    queryKey: queryKeys.recordings.detail(id),
    queryFn: () => api.fetchRecording(id),
    enabled: !!id,
    ...options,
  });
}

export function useRecordingSearch(
  query: string,
  options?: Partial<UseQueryOptions<PaginatedResponse<RecordingSummary>>>,
) {
  return useQuery({
    queryKey: queryKeys.recordings.search(query),
    queryFn: () => api.searchRecordings(query),
    enabled: query.length > 0,
    ...options,
  });
}

// -- Participants -----------------------------------------------------------

export function useParticipants(
  options?: Partial<UseQueryOptions<PaginatedResponse<Participant>>>,
) {
  return useQuery({
    queryKey: queryKeys.participants.list(),
    queryFn: () => api.fetchParticipants(),
    ...options,
  });
}

export function useParticipant(
  id: string,
  options?: Partial<UseQueryOptions<ParticipantWithRecordings>>,
) {
  return useQuery({
    queryKey: queryKeys.participants.detail(id),
    queryFn: () => api.fetchParticipant(id),
    enabled: !!id,
    ...options,
  });
}

// -- Tags -------------------------------------------------------------------

export function useTags(
  options?: Partial<UseQueryOptions<Tag[]>>,
) {
  return useQuery({
    queryKey: queryKeys.tags.list(),
    queryFn: () => api.fetchTags(),
    ...options,
  });
}

// -- Sync runs --------------------------------------------------------------

export function useSyncRuns(
  filters: SyncRunFilters = {},
  options?: Partial<UseQueryOptions<PaginatedResponse<SyncRunSummary>>>,
) {
  return useQuery({
    queryKey: queryKeys.syncRuns.list(filters),
    queryFn: () => api.fetchSyncRuns(filters),
    ...options,
  });
}

export function useSyncRun(
  id: string,
  options?: Partial<UseQueryOptions<SyncRunDetail>>,
) {
  return useQuery({
    queryKey: queryKeys.syncRuns.detail(id),
    queryFn: () => api.fetchSyncRun(id),
    enabled: !!id,
    ...options,
  });
}

// -- User -------------------------------------------------------------------

export function useCurrentUser(
  options?: Partial<UseQueryOptions<UserProfile>>,
) {
  return useQuery({
    queryKey: queryKeys.user.current,
    queryFn: () => api.fetchCurrentUser(),
    ...options,
  });
}

// -- Version ----------------------------------------------------------------

export function useVersion(
  options?: Partial<UseQueryOptions<string>>,
) {
  return useQuery({
    queryKey: queryKeys.version.current,
    queryFn: () => api.fetchVersion(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

// -- Search history ---------------------------------------------------------

export function useSearchHistory(
  options?: Partial<UseQueryOptions<{ data: SearchHistoryItem[] }>>,
) {
  return useQuery({
    queryKey: queryKeys.searchHistory.list(),
    queryFn: () => api.fetchSearchHistory(),
    ...options,
  });
}

// -- Analysis templates -----------------------------------------------------

export function useAnalysisTemplates(
  options?: Partial<UseQueryOptions<AnalysisTemplate[]>>,
) {
  return useQuery({
    queryKey: queryKeys.analysisTemplates.list(),
    queryFn: () => api.fetchAnalysisTemplates(),
    ...options,
  });
}

// =============================================================================
// Mutation hooks
// =============================================================================

// -- Recordings -------------------------------------------------------------

export function useUpdateRecording() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: UpdateRecordingRequest;
    }) => api.updateRecording(id, body),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: queryKeys.recordings.all });
      void qc.invalidateQueries({
        queryKey: queryKeys.recordings.detail(variables.id),
      });
    },
  });
}

export function useDeleteRecording() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteRecording(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.recordings.all });
    },
  });
}

export function useUploadRecording() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      title,
      recordedAt,
    }: {
      file: File;
      title?: string;
      recordedAt?: string;
    }) => api.uploadRecording(file, title, recordedAt),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.recordings.all });
    },
  });
}

export function usePasteTranscript() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PasteTranscriptRequest) => api.pasteTranscript(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.recordings.all });
    },
  });
}

export function useReprocessRecording() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.reprocessRecording(id),
    onSuccess: (_data, id) => {
      void qc.invalidateQueries({ queryKey: queryKeys.recordings.all });
      void qc.invalidateQueries({
        queryKey: queryKeys.recordings.detail(id),
      });
    },
  });
}

// -- Speakers ---------------------------------------------------------------

export function useAssignSpeaker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      recordingId,
      speakerLabel,
      body,
    }: {
      recordingId: string;
      speakerLabel: string;
      body: AssignSpeakerRequest;
    }) => api.assignSpeaker(recordingId, speakerLabel, body),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({
        queryKey: queryKeys.recordings.detail(variables.recordingId),
      });
      void qc.invalidateQueries({ queryKey: queryKeys.participants.all });
    },
  });
}

export function useDismissSpeaker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      recordingId,
      speakerLabel,
    }: {
      recordingId: string;
      speakerLabel: string;
    }) => api.dismissSpeaker(recordingId, speakerLabel),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({
        queryKey: queryKeys.recordings.detail(variables.recordingId),
      });
    },
  });
}

// -- Participants -----------------------------------------------------------

export function useCreateParticipant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateParticipantRequest) =>
      api.createParticipant(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.participants.all });
    },
  });
}

export function useUpdateParticipant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: UpdateParticipantRequest;
    }) => api.updateParticipant(id, body),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: queryKeys.participants.all });
      void qc.invalidateQueries({
        queryKey: queryKeys.participants.detail(variables.id),
      });
    },
  });
}

export function useDeleteParticipant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteParticipant(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.participants.all });
    },
  });
}

export function useMergeParticipants() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      targetId,
      sourceId,
    }: {
      targetId: string;
      sourceId: string;
    }) => api.mergeParticipants(targetId, sourceId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.participants.all });
      void qc.invalidateQueries({ queryKey: queryKeys.recordings.all });
    },
  });
}

// -- Tags -------------------------------------------------------------------

export function useCreateTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateTagRequest) => api.createTag(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.tags.all });
    },
  });
}

export function useUpdateTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateTagRequest }) =>
      api.updateTag(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.tags.all });
    },
  });
}

export function useDeleteTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteTag(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.tags.all });
      void qc.invalidateQueries({ queryKey: queryKeys.recordings.all });
    },
  });
}

export function useAddTagToRecording() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      recordingId,
      tagId,
    }: {
      recordingId: string;
      tagId: string;
    }) => api.addTagToRecording(recordingId, tagId),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: queryKeys.recordings.all });
      void qc.invalidateQueries({
        queryKey: queryKeys.recordings.detail(variables.recordingId),
      });
    },
  });
}

export function useRemoveTagFromRecording() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      recordingId,
      tagId,
    }: {
      recordingId: string;
      tagId: string;
    }) => api.removeTagFromRecording(recordingId, tagId),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: queryKeys.recordings.all });
      void qc.invalidateQueries({
        queryKey: queryKeys.recordings.detail(variables.recordingId),
      });
    },
  });
}

// -- Sync -------------------------------------------------------------------

export function useTriggerSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerSync(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.syncRuns.all });
    },
  });
}

export function usePollTranscriptions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.pollTranscriptions(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.syncRuns.all });
      void qc.invalidateQueries({ queryKey: queryKeys.recordings.all });
    },
  });
}

// -- AI / Chat / Analysis ---------------------------------------------------

export function useChatWithTranscript() {
  return useMutation<ChatResponse, Error, ChatRequest>({
    mutationFn: (body) => api.chatWithTranscript(body),
  });
}

export function useRunAnalysis() {
  return useMutation<
    AnalysisResponse,
    Error,
    { recordingId: string; body: AnalysisRequest }
  >({
    mutationFn: ({ recordingId, body }) =>
      api.runAnalysis(recordingId, body),
  });
}

// -- Analysis templates -----------------------------------------------------

export function useCreateAnalysisTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateAnalysisTemplateRequest) =>
      api.createAnalysisTemplate(body),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: queryKeys.analysisTemplates.all,
      });
    },
  });
}

export function useUpdateAnalysisTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: UpdateAnalysisTemplateRequest;
    }) => api.updateAnalysisTemplate(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: queryKeys.analysisTemplates.all,
      });
    },
  });
}

export function useDeleteAnalysisTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteAnalysisTemplate(id),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: queryKeys.analysisTemplates.all,
      });
    },
  });
}

// -- Settings ---------------------------------------------------------------

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateSettingsRequest) => api.updateSettings(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.user.current });
    },
  });
}

// =============================================================================
// Collections
// =============================================================================

export function useCollections(
  options?: Partial<UseQueryOptions<Collection[]>>,
) {
  return useQuery({
    queryKey: queryKeys.collections.list(),
    queryFn: () => api.fetchCollections(),
    ...options,
  });
}

export function useCollection(
  id: string,
  options?: Partial<UseQueryOptions<CollectionDetail>>,
) {
  return useQuery({
    queryKey: queryKeys.collections.detail(id),
    queryFn: () => api.fetchCollection(id),
    enabled: !!id,
    ...options,
  });
}

export function useCollectionSearches(
  id: string,
  options?: Partial<UseQueryOptions<CollectionSearchRecord[]>>,
) {
  return useQuery({
    queryKey: queryKeys.collections.searches(id),
    queryFn: () => api.fetchCollectionSearches(id),
    enabled: !!id,
    ...options,
  });
}

export function useCreateCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      api.createCollection(name, description),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.collections.all });
    },
  });
}

export function useUpdateCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: { name?: string; description?: string };
    }) => api.updateCollection(id, body),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: queryKeys.collections.all });
      void qc.invalidateQueries({
        queryKey: queryKeys.collections.detail(variables.id),
      });
    },
  });
}

export function useDeleteCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteCollection(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.collections.all });
    },
  });
}

export function useAddItemsToCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      collectionId,
      recordingIds,
    }: {
      collectionId: string;
      recordingIds: string[];
    }) => api.addItemsToCollection(collectionId, recordingIds),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: queryKeys.collections.all });
      void qc.invalidateQueries({
        queryKey: queryKeys.collections.detail(variables.collectionId),
      });
    },
  });
}

export function useRemoveItemFromCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      collectionId,
      recordingId,
    }: {
      collectionId: string;
      recordingId: string;
    }) => api.removeItemFromCollection(collectionId, recordingId),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: queryKeys.collections.all });
      void qc.invalidateQueries({
        queryKey: queryKeys.collections.detail(variables.collectionId),
      });
    },
  });
}

export function useCreateCollectionFromCandidates() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      name,
      recordingIds,
    }: {
      name: string;
      recordingIds: string[];
    }) => api.createCollectionFromCandidates(name, recordingIds),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.collections.all });
    },
  });
}
