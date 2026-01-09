import { useState, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { makeStyles } from '@fluentui/react-components';
import { PeopleActionBar } from './PeopleActionBar';
import { PeopleList } from './PeopleList';
import { ParticipantDetailPanel } from './ParticipantDetailPanel';
import { AddParticipantDialog } from './AddParticipantDialog';
import { ResizableSplitter } from '../layout/ResizableSplitter';
import { useParticipants } from '../../hooks/useParticipants';
import { useParticipantDetails } from '../../hooks/useParticipantDetails';
import { usePeopleList, type SortBy, type SortOrder } from '../../hooks/usePeopleList';
import { participantsService } from '../../services/participantsService';
import { showToast } from '../../utils/toast';
import type { UpdateParticipantRequest, CreateParticipantRequest } from '../../types';

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
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  // Data fetching - list
  const { participants, loading, refetch } = useParticipants();

  // Data fetching - selected participant details
  const {
    participant: selectedParticipant,
    recordings: participantRecordings,
    totalRecordings,
    loading: detailsLoading,
    refetch: refetchDetails,
  } = useParticipantDetails(selectedParticipantId);

  // Find the existing "Me" participant
  const existingMeParticipant = useMemo(() => {
    return participants.find(p => p.isUser) || null;
  }, [participants]);

  // Filtered and sorted list
  const { filteredParticipants, uniqueGroups } = usePeopleList(
    participants,
    searchQuery,
    sortBy,
    sortOrder,
    groupFilter
  );

  // Handle recording click - navigate to transcripts view with that recording selected
  const handleRecordingClick = useCallback((recordingId: string) => {
    window.dispatchEvent(new CustomEvent('navigateToRecording', {
      detail: { recordingId }
    }));
  }, []);

  // Handle save participant
  const handleSaveParticipant = useCallback(async (
    participantId: string,
    updates: UpdateParticipantRequest
  ) => {
    setSaving(true);
    let oldMeRemoved = false;
    try {
      // If setting isUser to true and there's an existing "Me" participant,
      // we need to first remove isUser from the existing one
      if (updates.isUser === true && existingMeParticipant && existingMeParticipant.id !== participantId) {
        await participantsService.updateParticipant(existingMeParticipant.id, { isUser: false });
        oldMeRemoved = true;
      }

      await participantsService.updateParticipant(participantId, updates);

      // Refetch both the list and details
      await Promise.all([refetch(), refetchDetails()]);

      showToast.success('Participant updated successfully');
    } catch (error) {
      // Rollback: Attempt to restore old "Me" if the second step failed
      if (oldMeRemoved && existingMeParticipant) {
        try {
          await participantsService.updateParticipant(existingMeParticipant.id, { isUser: true });
          await refetch();
        } catch (rollbackError) {
          console.error('Failed to rollback Me status', rollbackError);
        }
      }
      showToast.error('Failed to update participant');
      throw error; // Re-throw so the detail panel knows to stay in edit mode
    } finally {
      setSaving(false);
    }
  }, [existingMeParticipant, refetch, refetchDetails]);

  // Handle add participant
  const handleAddParticipant = useCallback(async (data: CreateParticipantRequest) => {
    setSaving(true);
    try {
      const newParticipant = await participantsService.createParticipant(data);

      // Refetch the list
      await refetch();

      // Select the newly created participant
      setSelectedParticipantId(newParticipant.id);

      showToast.success('Participant created successfully');
    } catch (error) {
      showToast.error('Failed to create participant');
      throw error; // Re-throw so the dialog knows to stay open
    } finally {
      setSaving(false);
    }
  }, [refetch, setSelectedParticipantId]);

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
        onAddPerson={() => setAddDialogOpen(true)}
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
        <ParticipantDetailPanel
          participant={selectedParticipant}
          recordings={participantRecordings}
          totalRecordings={totalRecordings}
          loading={detailsLoading}
          onRecordingClick={handleRecordingClick}
          onSave={handleSaveParticipant}
          existingMeParticipant={existingMeParticipant}
          saving={saving}
        />
      </div>

      {/* Add Person Dialog */}
      <AddParticipantDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        onSave={handleAddParticipant}
        saving={saving}
      />
    </div>
  );
}
