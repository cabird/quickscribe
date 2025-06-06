import React, { useState, useEffect } from 'react';
import { MultiSelect, Group, Text, ColorSwatch } from '@mantine/core';
import { Tag } from '../interfaces/Models';
import { fetchUserTags } from '../api/tags';
import { notifications } from '@mantine/notifications';

interface TagSelectorProps {
    selectedTagIds: string[];
    onTagsChange: (tagIds: string[]) => void;
    disabled?: boolean;
}

const TagSelector: React.FC<TagSelectorProps> = ({ 
    selectedTagIds, 
    onTagsChange, 
    disabled = false 
}) => {
    const [userTags, setUserTags] = useState<Tag[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const loadUserTags = async () => {
            try {
                const tags = await fetchUserTags();
                setUserTags(tags);
            } catch (error) {
                console.error('Failed to load user tags:', error);
                notifications.show({
                    title: 'Error',
                    message: 'Failed to load tags',
                    color: 'red'
                });
            } finally {
                setLoading(false);
            }
        };

        loadUserTags();
    }, []);

    const tagOptions = userTags.map(tag => ({
        value: tag.id,
        label: tag.name,
        color: tag.color
    }));

    const renderSelectOption = ({ option }: { option: any }) => (
        <Group gap="sm">
            <ColorSwatch color={option.color} size={16} />
            <Text size="sm">{option.label}</Text>
        </Group>
    );

    const renderValue = ({ value, label, onRemove, classNames, ...others }: any) => {
        const tag = userTags.find(t => t.id === value);
        if (!tag) return null;
        
        return (
            <div
                style={{
                    backgroundColor: tag.color,
                    color: 'white',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '12px',
                    margin: '1px'
                }}
                {...others}
            >
                <span>{tag.name}</span>
                {onRemove && (
                    <button
                        onClick={onRemove}
                        style={{
                            background: 'none',
                            border: 'none',
                            color: 'white',
                            cursor: 'pointer',
                            padding: '0',
                            marginLeft: '4px',
                            fontSize: '14px',
                            lineHeight: 1
                        }}
                    >
                        ×
                    </button>
                )}
            </div>
        );
    };

    return (
        <MultiSelect
            label="Tags"
            placeholder={loading ? "Loading tags..." : "Select tags"}
            data={tagOptions}
            value={selectedTagIds}
            onChange={onTagsChange}
            disabled={disabled || loading}
            searchable
            clearable
            renderOption={renderSelectOption}
            valueComponent={renderValue}
            maxDropdownHeight={200}
            size="sm"
        />
    );
};

export default TagSelector;