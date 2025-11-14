import { useState, KeyboardEvent } from 'react';
import { makeStyles, Textarea, Button, tokens } from '@fluentui/react-components';
import { Send24Regular } from '@fluentui/react-icons';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    gap: '8px',
    alignItems: 'flex-end',
  },
  textarea: {
    flex: 1,
  },
  sendButton: {
    flexShrink: 0,
  },
});

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const styles = useStyles();
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={styles.container}>
      <Textarea
        className={styles.textarea}
        placeholder="Ask a question about this transcript..."
        value={input}
        onChange={(_, data) => setInput(data.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        resize="vertical"
        rows={2}
      />
      <Button
        className={styles.sendButton}
        appearance="primary"
        icon={<Send24Regular />}
        onClick={handleSend}
        disabled={disabled || !input.trim()}
      >
        Send
      </Button>
    </div>
  );
}
