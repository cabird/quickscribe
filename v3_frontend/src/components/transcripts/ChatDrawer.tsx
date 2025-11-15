import { useState, useRef, useEffect } from 'react';
import { makeStyles, Button, tokens } from '@fluentui/react-components';
import { Dismiss24Regular, Delete24Regular, Subtract24Regular } from '@fluentui/react-icons';
import { ChatMessage as ChatMessageComponent } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { chatService, type ChatMessage } from '../../services/chatService';
import { generateRefId } from '../../utils/chatUtils';
import { showToast } from '../../utils/toast';

const useStyles = makeStyles({
  drawer: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    backgroundColor: tokens.colorNeutralBackground1,
    borderLeft: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 24px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    flexShrink: 0,
  },
  title: {
    fontSize: tokens.fontSizeBase400,
    fontWeight: tokens.fontWeightSemibold,
  },
  headerButtons: {
    display: 'flex',
    gap: '8px',
  },
  messagesContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    minHeight: 0,
  },
  inputContainer: {
    padding: '16px 24px',
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    flexShrink: 0,
  },
});

interface ChatDrawerProps {
  transcriptionId: string;
  transcriptEntries: Array<{ speaker: string; text: string }>;
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  onClose: () => void;
  onMinimize: () => void;
  onRefClick: (transcriptIndex: number) => void;
}

export function ChatDrawer({ transcriptionId, transcriptEntries, messages, onMessagesChange, onClose, onMinimize, onRefClick }: ChatDrawerProps) {
  const styles = useStyles();
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Generate ref mapping when drawer opens
  const refMapping = useRef<Map<string, number>>(new Map());
  const availableRefs = useRef<string[]>([]);

  useEffect(() => {
    // Build ref mapping: refId -> transcript index
    transcriptEntries.forEach((_entry, index) => {
      const refId = generateRefId(index);
      refMapping.current.set(refId, index);
      availableRefs.current.push(refId);
    });

    // Build tagged transcript for system message
    const taggedTranscript = transcriptEntries
      .map((entry, index) => {
        const refId = generateRefId(index);
        return `[[${refId}]] ${entry.speaker}: ${entry.text}`;
      })
      .join('\n\n');

    // Initialize with system message only if messages are empty
    if (messages.length === 0) {
      onMessagesChange([
        {
          role: 'system',
          content: `You are analyzing a transcript. Each paragraph is tagged with a unique reference ID in the format [[ref_AB01]].

IMPORTANT: When citing multiple parts of the transcript, you MUST write each reference tag separately with its own double brackets. For example:
- CORRECT: "This was discussed in [[ref_AB01]] and [[ref_AB05]]"
- WRONG: "This was discussed in [[ref_AB01], [ref_AB05]]"
- WRONG: "This was discussed in [[ref_AB01, ref_AB05]]"

Always include the full [[ref_XX##]] format for each reference, even when citing multiple passages.

Transcript:
${taggedTranscript}`,
        },
      ]);
    }
  }, [transcriptEntries, messages.length, onMessagesChange]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (userMessage: string) => {
    if (!userMessage.trim()) return;

    // Add user message
    const newMessages: ChatMessage[] = [
      ...messages,
      { role: 'user', content: userMessage },
    ];
    onMessagesChange(newMessages);
    setIsLoading(true);

    try {
      // Call chat service (mock for now)
      const response = await chatService.chat(transcriptionId, newMessages, availableRefs.current);

      // Add assistant response
      onMessagesChange([
        ...newMessages,
        { role: 'assistant', content: response.message },
      ]);
    } catch (error) {
      showToast.apiError(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    // Keep only the system message
    onMessagesChange([messages[0]]);
  };

  const handleRefClick = (refId: string) => {
    const transcriptIndex = refMapping.current.get(refId);
    if (transcriptIndex !== undefined) {
      onRefClick(transcriptIndex);
    }
  };

  return (
    <div className={styles.drawer}>
      <div className={styles.header}>
        <span className={styles.title}>Chat with Transcript</span>
        <div className={styles.headerButtons}>
          <Button
            appearance="subtle"
            icon={<Delete24Regular />}
            onClick={handleClear}
            disabled={messages.length <= 1}
            title="Clear conversation"
          />
          <Button
            appearance="subtle"
            icon={<Subtract24Regular />}
            onClick={onMinimize}
            title="Minimize"
          />
          <Button
            appearance="subtle"
            icon={<Dismiss24Regular />}
            onClick={onClose}
            title="Close"
          />
        </div>
      </div>

      <div className={styles.messagesContainer}>
        {messages.slice(1).map((message, index) => (
          <ChatMessageComponent
            key={index}
            message={message}
            refMapping={refMapping.current}
            transcriptEntries={transcriptEntries}
            onRefClick={handleRefClick}
          />
        ))}
        {isLoading && (
          <ChatMessageComponent
            message={{ role: 'assistant', content: 'Thinking...' }}
            refMapping={refMapping.current}
            transcriptEntries={transcriptEntries}
            onRefClick={handleRefClick}
            isLoading
          />
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className={styles.inputContainer}>
        <ChatInput onSend={handleSendMessage} disabled={isLoading} />
      </div>
    </div>
  );
}
