import { Badge, ActionIcon } from '@mantine/core';
import { IconX } from '@tabler/icons-react';
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
        backgroundColor: `${tag.color}15`,
        color: tag.color,
        border: `1px solid ${tag.color}40`,
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
            <IconX size={size === 'xs' ? 8 : 10} />
          </ActionIcon>
        ) : undefined
      }
    >
      {tag.name}
    </Badge>
  );
}