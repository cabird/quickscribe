import { apiClient } from './api';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  message: string;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
  responseTimeMs?: number;
}

// Real chat service supporting single or multiple transcription IDs
const realChatService = {
  /**
   * Chat with one or more transcriptions
   * @param transcriptionIds - Single ID or array of IDs
   * @param messages - Chat messages including system prompt
   */
  async chat(transcriptionIds: string | string[], messages: ChatMessage[]): Promise<ChatResponse> {
    // Normalize to array and use appropriate API parameter
    const idsArray = Array.isArray(transcriptionIds) ? transcriptionIds : [transcriptionIds];

    const response = await apiClient.post('/api/ai/chat', {
      // Use transcription_ids for multiple, transcription_id for backwards compat with single
      ...(idsArray.length === 1
        ? { transcription_id: idsArray[0] }
        : { transcription_ids: idsArray }),
      messages
    });
    return response.data;
  }
};

// Export chat service
export const chatService = {
  /**
   * Chat with transcription(s)
   * @param transcriptionIds - Single ID or array of IDs
   * @param messages - Chat messages
   * @param _availableRefs - Optional refs (currently unused)
   */
  chat: (transcriptionIds: string | string[], messages: ChatMessage[], _availableRefs?: string[]) =>
    realChatService.chat(transcriptionIds, messages)
};
