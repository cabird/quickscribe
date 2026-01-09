import { useState, useRef, useEffect } from 'react';
import { makeStyles, mergeClasses, tokens, Input } from '@fluentui/react-components';

const useStyles = makeStyles({
  container: {
    position: 'relative',
  },
  dropdown: {
    position: 'absolute',
    top: '100%',
    left: 0,
    zIndex: 100,
    backgroundColor: 'white',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: '6px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    minWidth: '200px',
    maxHeight: '250px',
    overflowY: 'auto',
    marginTop: '4px',
  },
  inputContainer: {
    padding: '8px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  item: {
    padding: '8px 12px',
    cursor: 'pointer',
    fontSize: '14px',
    ':hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  itemHighlighted: {
    backgroundColor: tokens.colorBrandBackground2,
  },
  itemNew: {
    color: tokens.colorBrandForeground1,
    fontWeight: 500,
  },
  emptyState: {
    padding: '8px 12px',
    fontSize: '14px',
    color: '#9CA3AF',
  },
});

interface SpeakerDropdownProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (name: string) => void;
  knownSpeakers: string[];
  children: React.ReactNode; // The trigger element
}

export function SpeakerDropdown({
  isOpen,
  onClose,
  onSelect,
  knownSpeakers,
  children,
}: SpeakerDropdownProps) {
  const styles = useStyles();
  const [searchText, setSearchText] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
        setSearchText('');
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      // Focus input when dropdown opens
      setTimeout(() => inputRef.current?.focus(), 0);
    }

    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onClose]);

  // Reset state when dropdown closes
  useEffect(() => {
    if (!isOpen) {
      setSearchText('');
      setHighlightedIndex(0);
    }
  }, [isOpen]);

  // Filter known speakers based on search text
  const filteredSpeakers = knownSpeakers.filter(name =>
    name.toLowerCase().includes(searchText.toLowerCase())
  );

  // Check if we should show "Add new" option
  const showAddNew = searchText.trim() &&
    !filteredSpeakers.some(s => s.toLowerCase() === searchText.toLowerCase());

  const handleSelectSpeaker = (name: string) => {
    onSelect(name);
    onClose();
    setSearchText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const totalItems = filteredSpeakers.length + (showAddNew ? 1 : 0);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex(i => (i + 1) % totalItems);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex(i => (i - 1 + totalItems) % totalItems);
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      // Tab or Enter selects the highlighted item
      if (totalItems > 0) {
        e.preventDefault();
        if (highlightedIndex < filteredSpeakers.length) {
          handleSelectSpeaker(filteredSpeakers[highlightedIndex]);
        } else if (showAddNew) {
          handleSelectSpeaker(searchText.trim());
        }
      }
    } else if (e.key === 'Escape') {
      onClose();
      setSearchText('');
    }
  };

  return (
    <div className={styles.container} ref={containerRef}>
      {children}

      {isOpen && (
        <div className={styles.dropdown}>
          <div className={styles.inputContainer}>
            <Input
              ref={inputRef}
              placeholder="Search or add speaker..."
              value={searchText}
              onChange={(_, data) => {
                setSearchText(data.value);
                setHighlightedIndex(0);
              }}
              onKeyDown={handleKeyDown}
              size="small"
              style={{ width: '100%' }}
            />
          </div>

          {/* Known speakers list */}
          {filteredSpeakers.map((name, index) => (
            <div
              key={name}
              className={mergeClasses(
                styles.item,
                index === highlightedIndex && styles.itemHighlighted
              )}
              onClick={() => handleSelectSpeaker(name)}
              onMouseEnter={() => setHighlightedIndex(index)}
            >
              {name}
            </div>
          ))}

          {/* Add new option */}
          {showAddNew && (
            <div
              className={mergeClasses(
                styles.item,
                styles.itemNew,
                highlightedIndex === filteredSpeakers.length && styles.itemHighlighted
              )}
              onClick={() => handleSelectSpeaker(searchText.trim())}
              onMouseEnter={() => setHighlightedIndex(filteredSpeakers.length)}
            >
              + Add "{searchText.trim()}"
            </div>
          )}

          {/* Empty state */}
          {filteredSpeakers.length === 0 && !showAddNew && (
            <div className={styles.emptyState}>
              Type to search or add...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
