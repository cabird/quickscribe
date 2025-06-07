import { Badge, ActionIcon } from '@mantine/core';
import { LuX } from 'react-icons/lu';
import type { Tag } from '../../types';

interface TagBadgeProps {
  tag: Tag;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  removable?: boolean;
  onRemove?: (tagId: string) => void;
}

export function TagBadge({ tag, size = 'sm', removable = false, onRemove }: TagBadgeProps) {
  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onRemove?.(tag.id);
  };

  return (
    <Badge
      size={size}
      variant="light"
      style={{
        background: `linear-gradient(135deg, ${tag.color}20, ${tag.color}10)`,
        color: tag.color,
        border: `1px solid ${tag.color}40`,
        backdropFilter: 'blur(8px)',
        fontWeight: 500,
        transition: 'all 0.2s ease',
      }}
      leftSection={
        <div
          style={{
            width: size === 'xs' ? 6 : 8,
            height: size === 'xs' ? 6 : 8,
            borderRadius: '50%',
            backgroundColor: tag.color,
          }}
        />
      }
      rightSection={
        removable ? (
          <ActionIcon
            size={size === 'xs' ? 12 : 16}
            variant="transparent"
            color={tag.color}
            onClick={handleRemove}
          >
            <LuX size={size === 'xs' ? 8 : 10} />
          </ActionIcon>
        ) : undefined
      }
    >
      {tag.name}
    </Badge>
  );
}