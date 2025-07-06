import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { TextInput, Paper, Text, ScrollArea, UnstyledButton, Group, Loader, Portal } from '@mantine/core';
import { useFloating, autoUpdate, offset, flip, shift } from '@floating-ui/react';
import { LuSearch, LuUserPlus, LuCheck } from 'react-icons/lu';
import { useParticipantStore } from '../../stores/participantStore';
import { useDebouncedValue } from '@mantine/hooks';

interface InlineParticipantPickerProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (participantId: string | 'new') => void;
  anchorRef: React.RefObject<HTMLElement>;
  currentParticipantId?: string;
}

export function InlineParticipantPicker({
  isOpen,
  onClose,
  onSelect,
  anchorRef,
  currentParticipantId
}: InlineParticipantPickerProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm] = useDebouncedValue(searchTerm, 200);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  
  const { participants, loading, fetchParticipants } = useParticipantStore();

  // Calculate position immediately based on click data
  const position = useMemo(() => {
    if (!isOpen) return { x: 0, y: 0 };
    
    const clickData = (window as any).lastSpeakerEditClick;
    if (!clickData) {
      // Fallback position
      return {
        x: Math.min(250, window.innerWidth - 260),
        y: Math.min(300, window.innerHeight - 310)
      };
    }
    
    // Use the click position which should be viewport-relative
    let x = clickData.rect.left || clickData.x;
    // Use the bottom of the clicked element
    let y = clickData.rect.bottom || (clickData.y + clickData.rect.height);
    y += 4; // Small gap below the element
    
    const dropdownHeight = 300;
    const dropdownWidth = 250;
    
    // Ensure dropdown stays within viewport
    if (y + dropdownHeight > window.innerHeight) {
      // Position above the element
      y = (clickData.rect.top || clickData.y) - dropdownHeight - 4;
    }
    
    if (x + dropdownWidth > window.innerWidth) {
      x = window.innerWidth - dropdownWidth - 8;
    }
    
    return { x, y };
  }, [isOpen]);
  
  // Clean up when closed
  useEffect(() => {
    if (!isOpen) {
      // Clean up click data when closing
      if (process.env.NODE_ENV === 'production') {
        delete (window as any).lastSpeakerEditClick;
      }
    }
  }, [isOpen]);

  // Don't fetch participants here - they should be pre-loaded by the parent component

  // Focus search input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 0);
    }
  }, [isOpen]);

  // Handle click outside to close
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      const dropdown = document.querySelector('[data-participant-picker]');
      
      // Check if click is outside the dropdown
      if (dropdown && !dropdown.contains(target)) {
        onClose();
      }
    };

    // Add a small delay to avoid closing immediately on open
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  // Handle Escape key globally when dropdown is open
  useEffect(() => {
    if (!isOpen) return;

    const handleGlobalEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        onClose();
      }
    };

    // Use capture phase with highest priority
    document.addEventListener('keydown', handleGlobalEscape, { capture: true, passive: false });
    return () => {
      document.removeEventListener('keydown', handleGlobalEscape, { capture: true });
    };
  }, [isOpen, onClose]);

  // Filter and sort participants with debounced search
  const filteredParticipants = useMemo(() => {
    const filtered = participants.filter(p => {
      const searchLower = debouncedSearchTerm.toLowerCase();
      if (!searchLower) return true;
      
      return (
        p.displayName.toLowerCase().includes(searchLower) ||
        p.firstName?.toLowerCase().includes(searchLower) ||
        p.lastName?.toLowerCase().includes(searchLower) ||
        p.email?.toLowerCase().includes(searchLower) ||
        p.organization?.toLowerCase().includes(searchLower) ||
        p.aliases.some(alias => alias.toLowerCase().includes(searchLower))
      );
    });

    // Sort alphabetically by display name
    return filtered.sort((a, b) => 
      a.displayName.toLowerCase().localeCompare(b.displayName.toLowerCase())
    );
  }, [participants, debouncedSearchTerm]);

  // Reset highlight when filtered results change
  useEffect(() => {
    setHighlightedIndex(0);
  }, [filteredParticipants.length]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    const itemCount = filteredParticipants.length + 1; // +1 for "Add new" option

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex(prev => (prev + 1) % itemCount);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex(prev => (prev - 1 + itemCount) % itemCount);
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightedIndex < filteredParticipants.length) {
          onSelect(filteredParticipants[highlightedIndex].id);
        } else {
          onSelect('new');
        }
        break;
      case 'Escape':
        e.preventDefault();
        onClose();
        break;
    }
  };

  // Scroll highlighted item into view
  useEffect(() => {
    if (listRef.current && highlightedIndex >= 0) {
      const items = listRef.current.querySelectorAll('[data-participant-item]');
      const item = items[highlightedIndex];
      if (item) {
        item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }, [highlightedIndex]);

  if (!isOpen) return null;

  return (
    <Portal>
      <div
        data-participant-picker
        style={{
          position: 'fixed',
          left: `${position.x}px`,
          top: `${position.y}px`,
          zIndex: 9999,
          width: '250px',
          maxHeight: '300px',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: 'white',
          border: '1px solid #ccc',
          borderRadius: '4px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          padding: '8px',
        }}
      >
      <TextInput
        ref={searchInputRef}
        placeholder="Search participants..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.currentTarget.value)}
        onKeyDown={handleKeyDown}
        leftSection={<LuSearch size={14} />}
        size="xs"
        mb="xs"
      />

      <ScrollArea style={{ flex: 1 }} viewportRef={listRef}>
        {loading && participants.length === 0 ? (
          <Group justify="center" p="md">
            <Loader size="sm" />
          </Group>
        ) : (
          <>
            {filteredParticipants.map((participant, index) => (
              <UnstyledButton
                key={participant.id}
                onClick={() => onSelect(participant.id)}
                onMouseEnter={() => setHighlightedIndex(index)}
                data-participant-item
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '6px 8px',
                  borderRadius: 4,
                  backgroundColor: highlightedIndex === index 
                    ? 'var(--mantine-color-blue-1)' 
                    : 'transparent',
                  transition: 'background-color 0.1s',
                }}
              >
                <Group justify="space-between" wrap="nowrap">
                  <div style={{ minWidth: 0 }}>
                    <Text size="sm" fw={500} truncate>
                      {participant.displayName}
                    </Text>
                    {(participant.role || participant.organization) && (
                      <Text size="xs" c="dimmed" truncate>
                        {[participant.role, participant.organization]
                          .filter(Boolean)
                          .join(' • ')}
                      </Text>
                    )}
                  </div>
                  {participant.id === currentParticipantId && (
                    <LuCheck size={14} style={{ color: 'var(--mantine-color-blue-6)' }} />
                  )}
                </Group>
              </UnstyledButton>
            ))}

            {/* Add new participant option */}
            <UnstyledButton
              onClick={() => onSelect('new')}
              onMouseEnter={() => setHighlightedIndex(filteredParticipants.length)}
              data-participant-item
              style={{
                display: 'block',
                width: '100%',
                padding: '6px 8px',
                borderRadius: 4,
                backgroundColor: highlightedIndex === filteredParticipants.length
                  ? 'var(--mantine-color-blue-1)'
                  : 'transparent',
                borderTop: '1px solid var(--mantine-color-gray-3)',
                marginTop: 4,
                paddingTop: 10,
              }}
            >
              <Group gap="xs">
                <LuUserPlus size={14} style={{ color: 'var(--mantine-color-blue-6)' }} />
                <Text size="sm" c="blue">Add new participant...</Text>
              </Group>
            </UnstyledButton>
          </>
        )}
      </ScrollArea>
      </div>
    </Portal>
  );
}