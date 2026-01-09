import { useMemo } from 'react';
import type { Participant } from '../types';

export type SortBy = 'name' | 'lastSeen' | 'firstSeen';
export type SortOrder = 'asc' | 'desc';

interface UsePeopleListResult {
  filteredParticipants: Participant[];
  uniqueGroups: string[];
}

export function usePeopleList(
  participants: Participant[],
  searchQuery: string,
  sortBy: SortBy,
  sortOrder: SortOrder,
  groupFilter: string
): UsePeopleListResult {
  return useMemo(() => {
    // Extract unique groups (organizations) for the filter dropdown
    const uniqueGroups = Array.from(
      new Set(
        participants
          .map(p => p.organization)
          .filter((org): org is string => !!org)
      )
    ).sort();

    // Filter participants
    let filtered = participants;

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(p => {
        // Search by displayName
        if (p.displayName.toLowerCase().includes(query)) return true;
        // Search by firstName
        if (p.firstName?.toLowerCase().includes(query)) return true;
        // Search by lastName
        if (p.lastName?.toLowerCase().includes(query)) return true;
        // Search by aliases
        if (p.aliases?.some(alias => alias.toLowerCase().includes(query))) return true;
        // Search by email
        if (p.email?.toLowerCase().includes(query)) return true;
        return false;
      });
    }

    // Apply group filter
    if (groupFilter) {
      filtered = filtered.filter(p => p.organization === groupFilter);
    }

    // Sort participants
    const sorted = [...filtered].sort((a, b) => {
      let comparison = 0;

      switch (sortBy) {
        case 'name':
          comparison = a.displayName.localeCompare(b.displayName);
          break;
        case 'lastSeen':
          comparison = new Date(b.lastSeen).getTime() - new Date(a.lastSeen).getTime();
          break;
        case 'firstSeen':
          comparison = new Date(a.firstSeen).getTime() - new Date(b.firstSeen).getTime();
          break;
      }

      return sortOrder === 'asc' ? comparison : -comparison;
    });

    return {
      filteredParticipants: sorted,
      uniqueGroups,
    };
  }, [participants, searchQuery, sortBy, sortOrder, groupFilter]);
}
