import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { makeStyles } from '@fluentui/react-components';
import { PeopleActionBar } from './PeopleActionBar';
import { PeopleList } from './PeopleList';
import { ParticipantDetailPanel } from './ParticipantDetailPanel';
import { ResizableSplitter } from '../layout/ResizableSplitter';
import { useParticipants } from '../../hooks/useParticipants';
import { usePeopleList, type SortBy, type SortOrder } from '../../hooks/usePeopleList';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    minHeight: 0,
  },
  viewContainer: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
    minHeight: 0,
  },
});

export function PeopleView() {
  const styles = useStyles();

  // URL-synced selection state
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedParticipantId = searchParams.get('selected');

  const setSelectedParticipantId = useCallback((id: string | null) => {
    const newParams = new URLSearchParams(searchParams);
    if (id) {
      newParams.set('selected', id);
    } else {
      newParams.delete('selected');
    }
    setSearchParams(newParams, { replace: true });
  }, [searchParams, setSearchParams]);

  // Local UI state
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<SortBy>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [groupFilter, setGroupFilter] = useState('');
  const [listPanelWidth, setListPanelWidth] = useState(35);

  // Data fetching
  const { participants, loading, refetch } = useParticipants();

  // Filtered and sorted list
  const { filteredParticipants, uniqueGroups } = usePeopleList(
    participants,
    searchQuery,
    sortBy,
    sortOrder,
    groupFilter
  );

  const handleResize = useCallback((delta: number) => {
    setListPanelWidth(prev => {
      const containerWidth = window.innerWidth - 68; // Subtract nav rail width
      const deltaPercent = (delta / containerWidth) * 100;
      const newWidth = prev + deltaPercent;
      // Constrain between 20% and 60%
      return Math.max(20, Math.min(60, newWidth));
    });
  }, []);

  return (
    <div className={styles.container}>
      <PeopleActionBar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        sortBy={sortBy}
        onSortByChange={setSortBy}
        sortOrder={sortOrder}
        onSortOrderChange={setSortOrder}
        groupFilter={groupFilter}
        onGroupFilterChange={setGroupFilter}
        uniqueGroups={uniqueGroups}
        onRefresh={refetch}
      />
      <div className={styles.viewContainer}>
        <PeopleList
          participants={filteredParticipants}
          selectedParticipantId={selectedParticipantId}
          onParticipantSelect={setSelectedParticipantId}
          loading={loading}
          width={listPanelWidth}
          totalCount={participants.length}
        />
        <ResizableSplitter onResize={handleResize} />
        <ParticipantDetailPanel selectedParticipantId={selectedParticipantId} />
      </div>
    </div>
  );
}
