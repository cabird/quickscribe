import { apiClient } from './api';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  message: string;
}

// Mock service for now - returns with random refs from transcript
const mockChatService = {
  async chat(messages: ChatMessage[], availableRefs: string[]): Promise<ChatResponse> {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Ensure we have at least 2 refs
    if (availableRefs.length < 2) {
      return {
        message: `Here's the answer to your query.`
      };
    }

    // Pick 2 random refs from available refs
    const shuffled = [...availableRefs].sort(() => Math.random() - 0.5);
    const ref1 = shuffled[0];
    const ref2 = shuffled[1];

    return {
      message: `Here's the answer to your query. This relates to [[${ref1}]] and also [[${ref2}]].`
    };
  }
};

// Real service (not implemented yet)
const realChatService = {
  async chat(messages: ChatMessage[]): Promise<ChatResponse> {
    const response = await apiClient.post('/api/ai/chat', { messages });
    return response.data;
  }
};

// Export mock for now - switch to real when backend is ready
export const chatService = {
  chat: (messages: ChatMessage[], availableRefs?: string[]) =>
    mockChatService.chat(messages, availableRefs || [])
};
