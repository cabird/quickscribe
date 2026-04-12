import axios, { type AxiosInstance } from "axios";
import { authEnabled, getAccessToken, getMsalInstance } from "./auth";
import type {
  AnalysisRequest,
  AnalysisResponse,
  AssignSpeakerRequest,
  ChatRequest,
  ChatResponse,
  Collection,
  CollectionDetail,
  CollectionSearchRecord,
  CreateAnalysisTemplateRequest,
  CreateParticipantRequest,
  CreateTagRequest,
  PaginatedResponse,
  Participant,
  ParticipantWithRecordings,
  PasteTranscriptRequest,
  RecordingDetail,
  RecordingFilters,
  RecordingSummary,
  RunLogsResponse,
  SearchHistoryItem,
  SearchToAddFilters,
  SearchToAddResult,
  SyncRunDetail,
  SyncRunFilters,
  SyncRunSummary,
  SyncTriggerResponse,
  Tag,
  UpdateParticipantRequest,
  UpdateRecordingRequest,
  UpdateSettingsRequest,
  UpdateTagRequest,
  UserProfile,
  AnalysisTemplate,
  UpdateAnalysisTemplateRequest,
  McpToken,
} from "@/types/models";

// ---------------------------------------------------------------------------
// Axios client
// ---------------------------------------------------------------------------

const baseURL = import.meta.env.VITE_API_URL ?? "";

const apiClient: AxiosInstance = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

// -- Request interceptor: attach Bearer token when auth is enabled ----------
apiClient.interceptors.request.use(async (config) => {
  if (authEnabled) {
    const token = await getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// -- Response interceptor: 401 triggers login redirect ----------------------
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && authEnabled) {
      const msal = getMsalInstance();
      const accounts = msal.getAllAccounts();
      if (accounts.length > 0) {
        // Clear cached tokens and force re-login
        await msal.logoutRedirect({ account: accounts[0] });
      }
    }
    return Promise.reject(error);
  },
);

// ---------------------------------------------------------------------------
// Typed API methods
// ---------------------------------------------------------------------------

// -- Recordings -------------------------------------------------------------

export async function fetchRecordings(
  filters: RecordingFilters = {},
): Promise<PaginatedResponse<RecordingSummary>> {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", String(filters.page));
  if (filters.per_page) params.set("per_page", String(filters.per_page));
  if (filters.search) params.set("search", filters.search);
  if (filters.status) params.set("status", filters.status);
  if (filters.source) params.set("source", filters.source);
  if (filters.tag_id) params.set("tag_id", filters.tag_id);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.sort_by) params.set("sort_by", filters.sort_by);
  if (filters.sort_order) params.set("sort_order", filters.sort_order);

  const { data } = await apiClient.get<PaginatedResponse<RecordingSummary>>(
    `/api/recordings`,
    { params },
  );
  return data;
}

export async function fetchRecording(
  id: string,
): Promise<RecordingDetail> {
  const { data } = await apiClient.get<RecordingDetail>(
    `/api/recordings/${id}`,
  );
  return data;
}

export async function updateRecording(
  id: string,
  body: UpdateRecordingRequest,
): Promise<RecordingDetail> {
  const { data } = await apiClient.put<RecordingDetail>(
    `/api/recordings/${id}`,
    body,
  );
  return data;
}

export async function deleteRecording(id: string): Promise<void> {
  await apiClient.delete(`/api/recordings/${id}`);
}

export async function uploadRecording(
  file: File,
  title?: string,
  recordedAt?: string,
): Promise<RecordingDetail> {
  const formData = new FormData();
  formData.append("file", file);
  if (title) formData.append("title", title);
  if (recordedAt) formData.append("recorded_at", recordedAt);

  const { data } = await apiClient.post<RecordingDetail>(
    `/api/recordings/upload`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function pasteTranscript(
  body: PasteTranscriptRequest,
): Promise<RecordingDetail> {
  const { data } = await apiClient.post<RecordingDetail>(
    `/api/recordings/paste`,
    body,
  );
  return data;
}

export async function fetchRecordingAudioUrl(
  id: string,
): Promise<{ url: string }> {
  const { data } = await apiClient.get<{ url: string }>(
    `/api/recordings/${id}/audio`,
  );
  return data;
}

export async function reprocessRecording(
  id: string,
): Promise<RecordingDetail> {
  const { data } = await apiClient.post<RecordingDetail>(
    `/api/recordings/${id}/reprocess`,
  );
  return data;
}

// -- Speakers (on recordings) -----------------------------------------------

export async function assignSpeaker(
  recordingId: string,
  speakerLabel: string,
  body: AssignSpeakerRequest,
): Promise<RecordingDetail> {
  const { data } = await apiClient.put<RecordingDetail>(
    `/api/recordings/${recordingId}/speakers/${encodeURIComponent(speakerLabel)}`,
    body,
  );
  return data;
}

export async function dismissSpeaker(
  recordingId: string,
  speakerLabel: string,
): Promise<RecordingDetail> {
  const { data } = await apiClient.post<RecordingDetail>(
    `/api/recordings/${recordingId}/speakers/${encodeURIComponent(speakerLabel)}/dismiss`,
  );
  return data;
}

// -- Participants -----------------------------------------------------------

export async function fetchParticipants(): Promise<
  PaginatedResponse<Participant>
> {
  const { data } =
    await apiClient.get<PaginatedResponse<Participant>>(`/api/participants?per_page=500`);
  return data;
}

export async function fetchParticipant(
  id: string,
): Promise<ParticipantWithRecordings> {
  const { data } = await apiClient.get<ParticipantWithRecordings>(
    `/api/participants/${id}`,
  );
  return data;
}

export async function createParticipant(
  body: CreateParticipantRequest,
): Promise<Participant> {
  const { data } = await apiClient.post<Participant>(
    `/api/participants`,
    body,
  );
  return data;
}

export async function updateParticipant(
  id: string,
  body: UpdateParticipantRequest,
): Promise<Participant> {
  const { data } = await apiClient.put<Participant>(
    `/api/participants/${id}`,
    body,
  );
  return data;
}

export async function deleteParticipant(id: string): Promise<void> {
  await apiClient.delete(`/api/participants/${id}`);
}

export async function searchParticipants(
  query: string,
): Promise<PaginatedResponse<Participant>> {
  const { data } = await apiClient.get<PaginatedResponse<Participant>>(
    `/api/participants/search`,
    { params: { name: query } },
  );
  return data;
}

export async function mergeParticipants(
  targetId: string,
  sourceId: string,
): Promise<Participant> {
  const { data } = await apiClient.post<Participant>(
    `/api/participants/${targetId}/merge/${sourceId}`,
  );
  return data;
}

// -- Tags -------------------------------------------------------------------

export async function fetchTags(): Promise<Tag[]> {
  const { data } = await apiClient.get<Tag[]>(`/api/tags`);
  return data;
}

export async function createTag(
  body: CreateTagRequest,
): Promise<Tag> {
  const { data } = await apiClient.post<Tag>(
    `/api/tags`,
    body,
  );
  return data;
}

export async function updateTag(
  id: string,
  body: UpdateTagRequest,
): Promise<Tag> {
  const { data } = await apiClient.put<Tag>(
    `/api/tags/${id}`,
    body,
  );
  return data;
}

export async function deleteTag(id: string): Promise<void> {
  await apiClient.delete(`/api/tags/${id}`);
}

export async function addTagToRecording(
  recordingId: string,
  tagId: string,
): Promise<void> {
  await apiClient.post(`/api/recordings/${recordingId}/tags/${tagId}`);
}

export async function removeTagFromRecording(
  recordingId: string,
  tagId: string,
): Promise<void> {
  await apiClient.delete(`/api/recordings/${recordingId}/tags/${tagId}`);
}

// -- AI ---------------------------------------------------------------------

export async function chatWithTranscript(
  body: ChatRequest,
): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>(
    `/api/ai/chat`,
    body,
  );
  return data;
}

export async function runAnalysis(
  recordingId: string,
  body: AnalysisRequest,
): Promise<AnalysisResponse> {
  const { data } = await apiClient.post<AnalysisResponse>(
    `/api/recordings/${recordingId}/analyze`,
    body,
  );
  return data;
}

// -- Analysis templates -----------------------------------------------------

export async function fetchAnalysisTemplates(): Promise<AnalysisTemplate[]> {
  const { data } = await apiClient.get<AnalysisTemplate[]>(
    `/api/me/analysis-templates`,
  );
  return data;
}

export async function createAnalysisTemplate(
  body: CreateAnalysisTemplateRequest,
): Promise<AnalysisTemplate> {
  const { data } = await apiClient.post<AnalysisTemplate>(
    `/api/me/analysis-templates`,
    body,
  );
  return data;
}

export async function updateAnalysisTemplate(
  id: string,
  body: UpdateAnalysisTemplateRequest,
): Promise<AnalysisTemplate> {
  const { data } = await apiClient.put<AnalysisTemplate>(
    `/api/me/analysis-templates/${id}`,
    body,
  );
  return data;
}

export async function deleteAnalysisTemplate(id: string): Promise<void> {
  await apiClient.delete(`/api/me/analysis-templates/${id}`);
}

// -- User / Settings --------------------------------------------------------

export async function fetchCurrentUser(): Promise<UserProfile> {
  const { data } =
    await apiClient.get<UserProfile>(`/api/me`);
  return data;
}

export async function updateSettings(
  body: UpdateSettingsRequest,
): Promise<UserProfile> {
  const { data } = await apiClient.put<UserProfile>(
    `/api/me/settings`,
    body,
  );
  return data;
}

// -- Speaker Reviews --------------------------------------------------------

export async function fetchSpeakerReviews(): Promise<{ data: RecordingDetail[] }> {
  const { data } = await apiClient.get<{ data: RecordingDetail[] }>(
    `/api/recordings/speaker-reviews`,
  );
  return data;
}

// -- Speaker Profiles -------------------------------------------------------

export async function rebuildSpeakerProfiles(): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>(
    `/api/me/speaker-profiles/rebuild`,
  );
  return data;
}

export async function identifySpeakers(recordingId: string): Promise<void> {
  await apiClient.post(`/api/recordings/${recordingId}/identify-speakers`);
}

export async function reidentifySpeakers(recordingId: string): Promise<void> {
  await apiClient.post(`/api/recordings/${recordingId}/reidentify`);
}

// -- Sync -------------------------------------------------------------------

export async function triggerSync(): Promise<SyncTriggerResponse> {
  const { data } = await apiClient.post<SyncTriggerResponse>(
    `/api/sync/trigger`,
  );
  return data;
}

export async function pollTranscriptions(): Promise<{ completed: string[]; count: number }> {
  const { data } = await apiClient.post<{ completed: string[]; count: number }>(
    `/api/sync/poll`,
  );
  return data;
}

export async function fetchSyncRuns(
  filters: SyncRunFilters = {},
): Promise<PaginatedResponse<SyncRunSummary>> {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", String(filters.page));
  if (filters.per_page) params.set("per_page", String(filters.per_page));
  if (filters.status) params.set("status", filters.status);
  if (filters.trigger) params.set("trigger", filters.trigger);
  if (filters.type) params.set("type", filters.type);

  const { data } = await apiClient.get<PaginatedResponse<SyncRunSummary>>(
    `/api/sync/runs`,
    { params },
  );
  return data;
}

export async function fetchSyncRun(
  id: string,
): Promise<SyncRunDetail> {
  const { data } = await apiClient.get<SyncRunDetail>(
    `/api/sync/runs/${id}`,
  );
  return data;
}

export async function fetchRunLogs(
  runId: string,
  afterId?: number,
): Promise<RunLogsResponse> {
  const params = new URLSearchParams();
  if (afterId !== undefined) params.set("after", String(afterId));

  const { data } = await apiClient.get<RunLogsResponse>(
    `/api/sync/runs/${runId}/logs`,
    { params },
  );
  return data;
}

// -- Version ----------------------------------------------------------------

export async function fetchVersion(): Promise<string> {
  // Use plain axios (no auth interceptor) — version is a public endpoint
  const base = apiClient.defaults.baseURL || "";
  const { data } = await axios.get<{ version: string }>(`${base}/api/version`);
  return data.version;
}

// -- Search History ---------------------------------------------------------

export async function fetchSearchHistory(
  limit = 20,
): Promise<{ data: SearchHistoryItem[] }> {
  const { data } = await apiClient.get<{ data: SearchHistoryItem[] }>(
    `/api/search/history`,
    { params: { limit } },
  );
  return data;
}

// -- Deep Search ------------------------------------------------------------

export function deepSearch(
  question: string,
  onEvent: (event: { event: string; data: string }) => void,
  getToken?: () => Promise<string | null>,
): { close: () => void } {
  // We can't use EventSource directly because it doesn't support POST or auth headers.
  // Use fetch with ReadableStream instead.
  const controller = new AbortController();

  (async () => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (getToken) {
      const token = await getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(`${baseURL}/api/search/deep`, {
        method: "POST",
        headers,
        body: JSON.stringify({ question }),
        signal: controller.signal,
      });

      if (!response.ok) {
        onEvent({ event: "error", data: `HTTP ${response.status}: ${response.statusText}` });
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? ""; // Keep incomplete last line

        let currentEvent = "";
        let currentData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7);
          } else if (line.startsWith("data: ")) {
            currentData = line.slice(6);
          } else if (line === "" && currentEvent) {
            onEvent({ event: currentEvent, data: currentData });
            currentEvent = "";
            currentData = "";
          }
        }
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        onEvent({ event: "error", data: String(err) });
      }
    }
  })();

  return { close: () => controller.abort() };
}

export async function generateMeetingNotes(
  recordingId: string,
): Promise<{ meeting_notes: string; meeting_notes_tags: string[] }> {
  const { data } = await apiClient.post<{ meeting_notes: string; meeting_notes_tags: string[] }>(
    `/api/recordings/${recordingId}/generate-meeting-notes`,
  );
  return data;
}

export async function generateSearchSummary(
  recordingId: string,
): Promise<{ summary: string; keywords: string[] }> {
  const { data } = await apiClient.post<{ summary: string; keywords: string[] }>(
    `/api/search/recordings/${recordingId}/generate-summary`,
  );
  return data;
}

// -- Search -----------------------------------------------------------------

export async function searchRecordings(
  query: string,
  page?: number,
  perPage?: number,
): Promise<PaginatedResponse<RecordingSummary>> {
  const params = new URLSearchParams({ q: query });
  if (page) params.set("page", String(page));
  if (perPage) params.set("per_page", String(perPage));

  const { data } = await apiClient.get<PaginatedResponse<RecordingSummary>>(
    `/api/recordings/search`,
    { params },
  );
  return data;
}

// -- Collections ------------------------------------------------------------

export async function fetchCollections(): Promise<Collection[]> {
  const { data } = await apiClient.get<Collection[]>(`/api/collections`);
  return data;
}

export async function createCollection(
  name: string,
  description?: string,
): Promise<Collection> {
  const { data } = await apiClient.post<Collection>(`/api/collections`, {
    name,
    description,
  });
  return data;
}

export async function fetchCollection(id: string): Promise<CollectionDetail> {
  const { data } = await apiClient.get<CollectionDetail>(
    `/api/collections/${id}`,
  );
  return data;
}

export async function updateCollection(
  id: string,
  body: { name?: string; description?: string },
): Promise<Collection> {
  const { data } = await apiClient.put<Collection>(
    `/api/collections/${id}`,
    body,
  );
  return data;
}

export async function deleteCollection(id: string): Promise<void> {
  await apiClient.delete(`/api/collections/${id}`);
}

export async function addItemsToCollection(
  id: string,
  recordingIds: string[],
): Promise<void> {
  await apiClient.post(`/api/collections/${id}/items`, {
    recording_ids: recordingIds,
  });
}

export async function removeItemFromCollection(
  collectionId: string,
  recordingId: string,
): Promise<void> {
  await apiClient.delete(
    `/api/collections/${collectionId}/items/${recordingId}`,
  );
}

export async function searchToAdd(
  collectionId: string,
  filters: SearchToAddFilters,
): Promise<SearchToAddResult[]> {
  const { data } = await apiClient.post<SearchToAddResult[]>(
    `/api/collections/${collectionId}/items/search`,
    filters,
  );
  return data;
}

export function searchCollection(
  collectionId: string,
  question: string,
  onEvent: (event: { event: string; data: string }) => void,
  getToken?: () => Promise<string | null>,
): { close: () => void } {
  const controller = new AbortController();

  (async () => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (getToken) {
      const token = await getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(
        `${baseURL}/api/collections/${collectionId}/search`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ question }),
          signal: controller.signal,
        },
      );

      if (!response.ok) {
        onEvent({
          event: "error",
          data: `HTTP ${response.status}: ${response.statusText}`,
        });
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        let currentEvent = "";
        let currentData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7);
          } else if (line.startsWith("data: ")) {
            currentData = line.slice(6);
          } else if (line === "" && currentEvent) {
            onEvent({ event: currentEvent, data: currentData });
            currentEvent = "";
            currentData = "";
          }
        }
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        onEvent({ event: "error", data: String(err) });
      }
    }
  })();

  return { close: () => controller.abort() };
}

export async function fetchCollectionSearches(
  collectionId: string,
): Promise<CollectionSearchRecord[]> {
  const { data } = await apiClient.get<CollectionSearchRecord[]>(
    `/api/collections/${collectionId}/searches`,
  );
  return data;
}

export function downloadCollectionUrl(id: string): string {
  return `${baseURL}/api/collections/${id}/download`;
}

export async function createCollectionFromCandidates(
  name: string,
  recordingIds: string[],
): Promise<Collection> {
  const { data } = await apiClient.post<Collection>(
    `/api/collections/from-candidates`,
    { name, recording_ids: recordingIds },
  );
  return data;
}

// -- MCP Tokens -------------------------------------------------------------

export async function listMcpTokens(): Promise<McpToken[]> {
  const { data } = await apiClient.get<McpToken[]>('/api/settings/mcp-tokens');
  return data;
}

export async function createMcpToken(name: string): Promise<McpToken> {
  const { data } = await apiClient.post<McpToken>('/api/settings/mcp-tokens', { name });
  return data;
}

export async function revokeMcpToken(tokenId: string): Promise<void> {
  await apiClient.delete(`/api/settings/mcp-tokens/${tokenId}`);
}
