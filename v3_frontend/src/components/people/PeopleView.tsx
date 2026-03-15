import { useState, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { makeStyles, Button } from '@fluentui/react-components';
import { ArrowLeft20Regular } from '@fluentui/react-icons';
import { PeopleActionBar } from './PeopleActionBar';
import { PeopleList } from './PeopleList';
import { ParticipantDetailPanel } from './ParticipantDetailPanel';
import { AddParticipantDialog } from './AddParticipantDialog';
import { DeleteConfirmDialog } from './DeleteConfirmDialog';
import { MergeParticipantDialog } from './MergeParticipantDialog';
import { ResizableSplitter } from '../layout/ResizableSplitter';
import { useParticipants } from '../../hooks/useParticipants';
import { useParticipantDetails } from '../../hooks/useParticipantDetails';
import { usePeopleList, type SortBy, type SortOrder } from '../../hooks/usePeopleList';
import { participantsService } from '../../services/participantsService';
import { showToast } from '../../utils/toast';
import { useIsMobile } from '../../hooks/useIsMobile';
import type { UpdateParticipantRequest, CreateParticipantRequest, Participant } from '../../types';

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
  mobileBackBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    borderBottom: '1px solid #e0e0e0',
    flexShrink: 0,
  },
  mobileBackTitle: {
    fontSize: '14px',
    fontWeight: 600,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    flex: 1,
  },
});

export function PeopleView() {
  const styles = useStyles();
  const isMobile = useIsMobile();

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

  // Bulk selection state
  const [checkedParticipantIds, setCheckedParticipantIds] = useState<Set<string>>(new Set());

  // Dialog states
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ participant: Participant; isBulk: boolean } | null>(null);
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);

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

  // Handle checkbox change for bulk selection
  const handleCheckChange = useCallback((participantId: string, checked: boolean) => {
    setCheckedParticipantIds(prev => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(participantId);
      } else {
        newSet.delete(participantId);
      }
      return newSet;
    });
  }, []);

  // Clear all checked selections
  const handleClearSelections = useCallback(() => {
    setCheckedParticipantIds(new Set());
  }, []);

  // Handle delete from detail panel
  const handleDeleteClick = useCallback((participant: Participant) => {
    setDeleteTarget({ participant, isBulk: false });
    setDeleteDialogOpen(true);
  }, []);

  // Handle bulk delete
  const handleBulkDeleteClick = useCallback(() => {
    // Get the first checked participant to show in the dialog
    const firstCheckedId = Array.from(checkedParticipantIds)[0];
    const firstChecked = participants.find(p => p.id === firstCheckedId);
    if (firstChecked) {
      setDeleteTarget({ participant: firstChecked, isBulk: true });
      setDeleteDialogOpen(true);
    }
  }, [checkedParticipantIds, participants]);

  // Confirm delete operation
  const handleConfirmDelete = useCallback(async () => {
    if (!deleteTarget) return;

    setSaving(true);
    try {
      if (deleteTarget.isBulk) {
        // Delete all checked participants
        const idsToDelete = Array.from(checkedParticipantIds);
        await Promise.all(idsToDelete.map(id => participantsService.deleteParticipant(id)));

        // Clear selection and checked items
        if (selectedParticipantId && checkedParticipantIds.has(selectedParticipantId)) {
          setSelectedParticipantId(null);
        }
        setCheckedParticipantIds(new Set());

        showToast.success(`Deleted ${idsToDelete.length} participant${idsToDelete.length > 1 ? 's' : ''}`);
      } else {
        // Delete single participant
        await participantsService.deleteParticipant(deleteTarget.participant.id);

        // Clear selection if the deleted participant was selected
        if (selectedParticipantId === deleteTarget.participant.id) {
          setSelectedParticipantId(null);
        }
        // Also remove from checked if it was checked
        if (checkedParticipantIds.has(deleteTarget.participant.id)) {
          setCheckedParticipantIds(prev => {
            const newSet = new Set(prev);
            newSet.delete(deleteTarget.participant.id);
            return newSet;
          });
        }

        showToast.success('Participant deleted');
      }

      // Refetch the list
      await refetch();
    } catch (error) {
      showToast.error('Failed to delete participant(s)');
    } finally {
      setSaving(false);
      setDeleteDialogOpen(false);
      setDeleteTarget(null);
    }
  }, [deleteTarget, checkedParticipantIds, selectedParticipantId, setSelectedParticipantId, refetch]);

  // Handle merge from detail panel
  const handleMergeClick = useCallback(() => {
    setMergeDialogOpen(true);
  }, []);

  // Confirm merge operation
  const handleConfirmMerge = useCallback(async (secondaryId: string) => {
    if (!selectedParticipant) return;

    setSaving(true);
    try {
      await participantsService.mergeParticipants(selectedParticipant.id, secondaryId);

      // Remove the merged participant from checked if it was checked
      if (checkedParticipantIds.has(secondaryId)) {
        setCheckedParticipantIds(prev => {
          const newSet = new Set(prev);
          newSet.delete(secondaryId);
          return newSet;
        });
      }

      // Refetch both list and details
      await Promise.all([refetch(), refetchDetails()]);

      showToast.success('Participants merged successfully');
      setMergeDialogOpen(false);
    } catch (error) {
      showToast.error('Failed to merge participants');
    } finally {
      setSaving(false);
    }
  }, [selectedParticipant, checkedParticipantIds, refetch, refetchDetails]);

  const handleMobileBack = useCallback(() => {
    setSelectedParticipantId(null);
  }, [setSelectedParticipantId]);

  const dialogs = (
    <>
      {/* Add Person Dialog */}
      <AddParticipantDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        onSave={handleAddParticipant}
        saving={saving}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        participant={deleteTarget?.participant || null}
        isBulk={deleteTarget?.isBulk || false}
        bulkCount={checkedParticipantIds.size}
        onConfirm={handleConfirmDelete}
        saving={saving}
      />

      {/* Merge Participant Dialog */}
      <MergeParticipantDialog
        open={mergeDialogOpen}
        onOpenChange={setMergeDialogOpen}
        primaryParticipant={selectedParticipant}
        participants={participants}
        onConfirm={handleConfirmMerge}
        saving={saving}
      />
    </>
  );

  // Mobile: single-panel navigation
  if (isMobile) {
    const showDetail = selectedParticipantId !== null;

    return (
      <div className={styles.container}>
        {showDetail ? (
          <>
            <div className={styles.mobileBackBar}>
              <Button
                appearance="subtle"
                icon={<ArrowLeft20Regular />}
                onClick={handleMobileBack}
              >
                Back
              </Button>
              <span className={styles.mobileBackTitle}>
                {selectedParticipant?.displayName || 'Person'}
              </span>
            </div>
            <ParticipantDetailPanel
              participant={selectedParticipant}
              recordings={participantRecordings}
              totalRecordings={totalRecordings}
              loading={detailsLoading}
              onRecordingClick={handleRecordingClick}
              onSave={handleSaveParticipant}
              existingMeParticipant={existingMeParticipant}
              saving={saving}
              onDelete={handleDeleteClick}
              onMerge={handleMergeClick}
            />
          </>
        ) : (
          <>
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
              selectedCount={checkedParticipantIds.size}
              onClearSelections={handleClearSelections}
              onDeleteSelected={handleBulkDeleteClick}
            />
            <PeopleList
              participants={filteredParticipants}
              selectedParticipantId={selectedParticipantId}
              onParticipantSelect={setSelectedParticipantId}
              loading={loading}
              width={100}
              totalCount={participants.length}
              checkedParticipantIds={checkedParticipantIds}
              onCheckChange={handleCheckChange}
            />
          </>
        )}
        {dialogs}
      </div>
    );
  }

  // Desktop: side-by-side list + detail
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
        selectedCount={checkedParticipantIds.size}
        onClearSelections={handleClearSelections}
        onDeleteSelected={handleBulkDeleteClick}
      />
      <div className={styles.viewContainer}>
        <PeopleList
          participants={filteredParticipants}
          selectedParticipantId={selectedParticipantId}
          onParticipantSelect={setSelectedParticipantId}
          loading={loading}
          width={listPanelWidth}
          totalCount={participants.length}
          checkedParticipantIds={checkedParticipantIds}
          onCheckChange={handleCheckChange}
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
          onDelete={handleDeleteClick}
          onMerge={handleMergeClick}
        />
      </div>
      {dialogs}
    </div>
  );
}
