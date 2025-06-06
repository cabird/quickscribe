import React from 'react';
import { Badge, CloseButton, Group } from '@mantine/core';
import { Tag } from '../interfaces/Models';

interface TagBadgeProps {
    tag: Tag;
    removable?: boolean;
    onRemove?: (tagId: string) => void;
    size?: 'xs' | 'sm' | 'md' | 'lg';
}

const TagBadge: React.FC<TagBadgeProps> = ({ 
    tag, 
    removable = false, 
    onRemove, 
    size = 'sm' 
}) => {
    return (
        <Badge
            color={tag.color}
            variant="filled"
            size={size}
            style={{
                backgroundColor: tag.color,
                color: '#ffffff'
            }}
        >
            <Group gap={4} wrap="nowrap">
                <span>{tag.name}</span>
                {removable && onRemove && (
                    <CloseButton
                        size="xs"
                        variant="transparent"
                        c="white"
                        onClick={(e) => {
                            e.stopPropagation();
                            onRemove(tag.id);
                        }}
                    />
                )}
            </Group>
        </Badge>
    );
};

export default TagBadge;