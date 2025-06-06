import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { Tag } from '../types';

interface TagState {
  tags: Tag[];
  loading: boolean;
  error: string | null;
  
  // Actions
  setTags: (tags: Tag[]) => void;
  addTag: (tag: Tag) => void;
  updateTag: (tag: Tag) => void;
  removeTag: (tagId: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  
  // Derived data
  getTagById: (id: string) => Tag | undefined;
  getTagsByIds: (ids: string[]) => Tag[];
}

export const useTagStore = create<TagState>()(
  devtools(
    (set, get) => ({
      tags: [],
      loading: false,
      error: null,

      setTags: (tags) =>
        set({ tags }, false, 'setTags'),

      addTag: (tag) =>
        set(
          (state) => ({
            tags: [...state.tags, tag],
          }),
          false,
          'addTag'
        ),

      updateTag: (updatedTag) =>
        set(
          (state) => ({
            tags: state.tags.map((tag) =>
              tag.id === updatedTag.id ? updatedTag : tag
            ),
          }),
          false,
          'updateTag'
        ),

      removeTag: (tagId) =>
        set(
          (state) => ({
            tags: state.tags.filter((tag) => tag.id !== tagId),
          }),
          false,
          'removeTag'
        ),

      setLoading: (loading) =>
        set({ loading }, false, 'setLoading'),

      setError: (error) =>
        set({ error }, false, 'setError'),

      // Derived data
      getTagById: (id) => {
        const state = get();
        return state.tags.find((tag) => tag.id === id);
      },

      getTagsByIds: (ids) => {
        const state = get();
        return state.tags.filter((tag) => ids.includes(tag.id));
      },
    }),
    {
      name: 'tag-store',
    }
  )
);