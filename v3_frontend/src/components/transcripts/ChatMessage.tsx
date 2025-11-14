import { makeStyles, mergeClasses, Text, Spinner, Tooltip, tokens } from '@fluentui/react-components';
import { Person24Regular, Bot24Regular } from '@fluentui/react-icons';
import type { ChatMessage as ChatMessageType } from '../../services/chatService';
import { formatMessageWithRefs } from '../../utils/chatUtils';

const useStyles = makeStyles({
  message: {
    display: 'flex',
    gap: '12px',
    alignItems: 'flex-start',
  },
  icon: {
    flexShrink: 0,
    marginTop: '4px',
  },
  userIcon: {
    color: tokens.colorBrandForeground1,
  },
  assistantIcon: {
    color: tokens.colorPaletteGreenForeground1,
  },
  content: {
    flex: 1,
  },
  messageText: {
    fontSize: tokens.fontSizeBase300,
    lineHeight: '1.6',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  userMessage: {
    color: tokens.colorNeutralForeground1,
  },
  assistantMessage: {
    color: tokens.colorNeutralForeground2,
  },
  refLink: {
    color: tokens.colorBrandForeground1,
    cursor: 'pointer',
    textDecoration: 'none',
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase200,
    verticalAlign: 'super',
    ':hover': {
      textDecoration: 'underline',
    },
  },
  loadingMessage: {
    fontStyle: 'italic',
    color: tokens.colorNeutralForeground3,
  },
});

interface ChatMessageProps {
  message: ChatMessageType;
  refMapping: Map<string, number>;
  transcriptEntries: Array<{ speaker: string; text: string }>;
  onRefClick: (refId: string) => void;
  isLoading?: boolean;
}

export function ChatMessage({ message, refMapping, transcriptEntries, onRefClick, isLoading }: ChatMessageProps) {
  const styles = useStyles();

  if (message.role === 'system') {
    return null; // Don't render system messages
  }

  const isUser = message.role === 'user';

  // Format message with refs
  const { displayText, references } = formatMessageWithRefs(message.content, refMapping);

  // Split text by reference markers and render with clickable links
  const renderTextWithRefs = () => {
    if (isLoading) {
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Spinner size="tiny" />
          <Text className={styles.loadingMessage}>{displayText}</Text>
        </div>
      );
    }

    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    const refPattern = /\[(\d+)\]/g;
    let match;

    while ((match = refPattern.exec(displayText)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        parts.push(displayText.substring(lastIndex, match.index));
      }

      // Add the clickable reference
      const displayNum = parseInt(match[1], 10);
      const ref = references.find(r => r.displayNum === displayNum);
      if (ref) {
        // Get the transcript text for this reference
        const transcriptIndex = refMapping.get(ref.refId);
        const transcriptEntry = transcriptIndex !== undefined ? transcriptEntries[transcriptIndex] : null;
        const tooltipText = transcriptEntry
          ? `${transcriptEntry.speaker}: ${transcriptEntry.text.substring(0, 200)}${transcriptEntry.text.length > 200 ? '...' : ''}`
          : 'Reference not found';

        parts.push(
          <Tooltip
            key={`ref-${match.index}`}
            content={tooltipText}
            relationship="description"
          >
            <a
              className={styles.refLink}
              onClick={(e) => {
                e.preventDefault();
                onRefClick(ref.refId);
              }}
              href="#"
            >
              [{displayNum}]
            </a>
          </Tooltip>
        );
      }

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < displayText.length) {
      parts.push(displayText.substring(lastIndex));
    }

    return parts.length > 0 ? parts : displayText;
  };

  return (
    <div className={styles.message}>
      <div className={styles.icon}>
        {isUser ? (
          <Person24Regular className={styles.userIcon} />
        ) : (
          <Bot24Regular className={styles.assistantIcon} />
        )}
      </div>
      <div className={styles.content}>
        <Text className={mergeClasses(styles.messageText, isUser ? styles.userMessage : styles.assistantMessage)}>
          {renderTextWithRefs()}
        </Text>
      </div>
    </div>
  );
}
