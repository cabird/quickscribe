// Main App Component - Two-Phase Flow
// Phase 1: Validate known speaker matches
// Phase 2: Identify and validate unknown speaker clusters
const { useState, useEffect, useCallback, useRef } = React;
const { Button, Toast, Dialog, ProgressSpinner } = PrimeReactBundle;
const { Icon, ValidationCard, IdentificationCard, ProgressHeader } = ValidationApp;

ValidationApp.App = function App() {
    const toast = React.useRef(null);

    // State
    const [loading, setLoading] = useState(true);
    const [queue, setQueue] = useState(null);
    const [existingParticipants, setExistingParticipants] = useState([]);

    // Phase tracking: "known_matches" or "unknown_clusters"
    const [currentPhase, setCurrentPhase] = useState('known_matches');

    // Known matches state
    const [currentParticipantIndex, setCurrentParticipantIndex] = useState(0);
    const [currentItemIndex, setCurrentItemIndex] = useState(0);

    // Unknown clusters state
    const [currentClusterIndex, setCurrentClusterIndex] = useState(0);
    const [clusterMode, setClusterMode] = useState('identify'); // 'identify' or 'confirm'
    const [currentClusterItemIndex, setCurrentClusterItemIndex] = useState(0);
    const [identifiedCluster, setIdentifiedCluster] = useState(null); // { participantId, participantName, items }

    // Session tracking
    const [decisions, setDecisions] = useState([]);
    const [sessionStarted, setSessionStarted] = useState(null);
    const [showBreakReminder, setShowBreakReminder] = useState(false);
    const [itemsValidatedInSession, setItemsValidatedInSession] = useState(0);
    const [undoStack, setUndoStack] = useState([]);

    // Load validation queue on mount
    useEffect(() => {
        loadQueue();
        loadParticipants();
    }, []);

    const loadQueue = async () => {
        setLoading(true);
        try {
            // Always reload to filter out already-validated items
            const response = await fetch('/api/validation-queue?reload=true');
            const data = await response.json();
            setQueue(data);
            setSessionStarted(new Date().toISOString());

            // Reset all indices to start fresh
            setCurrentParticipantIndex(0);
            setCurrentItemIndex(0);
            setCurrentClusterIndex(0);
            setCurrentClusterItemIndex(0);
            setClusterMode('identify');
            setIdentifiedCluster(null);

            // Debug logging
            console.log('Queue loaded:', {
                participants: data.participants?.length || 0,
                firstParticipantItems: data.participants?.[0]?.items?.length || 0,
                clusters: data.unknown_clusters?.length || 0,
                totalItems: data.total_items,
                totalClusterItems: data.total_cluster_items
            });

            // Determine starting phase - check for actual items, not just array length
            const hasKnownItems = data.participants && data.participants.some(p => p.items && p.items.length > 0);
            if (hasKnownItems) {
                setCurrentPhase('known_matches');
            } else if (data.unknown_clusters && data.unknown_clusters.length > 0) {
                setCurrentPhase('unknown_clusters');
            }

            if (toast.current) {
                const knownCount = data.total_items || 0;
                const clusterCount = data.total_cluster_items || 0;
                toast.current.show({
                    severity: 'info',
                    summary: 'Queue Loaded',
                    detail: `${knownCount} known matches, ${clusterCount} unknown speakers in ${data.unknown_clusters?.length || 0} clusters`,
                    life: 4000
                });
            }
        } catch (error) {
            console.error('Error loading queue:', error);
            if (toast.current) {
                toast.current.show({
                    severity: 'error',
                    summary: 'Error',
                    detail: 'Failed to load validation queue',
                    life: 5000
                });
            }
        } finally {
            setLoading(false);
        }
    };

    const loadParticipants = async () => {
        try {
            const response = await fetch('/api/participants');
            const data = await response.json();
            setExistingParticipants(data.participants || []);
        } catch (error) {
            console.error('Error loading participants:', error);
        }
    };

    // Create a new participant
    const handleCreateParticipant = async (displayName) => {
        try {
            const response = await fetch('/api/create-participant', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ displayName: displayName })
            });
            const result = await response.json();
            if (result.success && result.participant) {
                // Refresh participants list
                loadParticipants();
                if (toast.current) {
                    toast.current.show({
                        severity: 'success',
                        summary: 'Participant Created',
                        detail: `Created "${result.participant.displayName}"`,
                        life: 3000
                    });
                }
                return result.participant;
            } else {
                throw new Error(result.error || 'Failed to create participant');
            }
        } catch (error) {
            console.error('Error creating participant:', error);
            if (toast.current) {
                toast.current.show({
                    severity: 'error',
                    summary: 'Error',
                    detail: 'Failed to create participant',
                    life: 5000
                });
            }
            throw error;
        }
    };

    // Handle decision for known matches
    const handleDecision = async (decision, assignedParticipantId, metadata = {}) => {
        if (!queue) return;

        const participant = queue.participants[currentParticipantIndex];
        if (!participant) return;

        const item = participant.items[currentItemIndex];
        if (!item) return;

        // Record decision with metadata
        const decisionRecord = {
            item_id: item.item_id,
            decision: decision,
            participant_id: assignedParticipantId || participant.participant_id,
            similarity: item.similarity,
            timestamp: new Date().toISOString(),
            phase: 'known_match',
            // Include training quality and reassignment info from metadata
            training_quality: metadata.trainingQuality ?? null,
            reassigned_from: metadata.reassignedFrom || null,
            reassigned_from_name: metadata.reassignedFromName || null,
            reassigned_to_name: metadata.reassignedToName || null
        };

        const newDecisions = [...decisions, decisionRecord];
        setDecisions(newDecisions);

        // Save immediately
        saveDecisionToServer(decisionRecord);

        // Add to undo stack
        setUndoStack([...undoStack, {
            phase: 'known_matches',
            participantIndex: currentParticipantIndex,
            itemIndex: currentItemIndex,
            decision: decisionRecord
        }]);

        // Increment items validated
        const newItemsValidated = itemsValidatedInSession + 1;
        setItemsValidatedInSession(newItemsValidated);

        // Check for break reminder
        if (newItemsValidated > 0 && newItemsValidated % 30 === 0) {
            setShowBreakReminder(true);
        }

        // Move to next item
        moveToNextKnownItem();
    };

    // Handle decision for cluster items
    const handleClusterDecision = async (decision, assignedParticipantId, metadata = {}) => {
        if (!identifiedCluster) return;

        const item = identifiedCluster.items[currentClusterItemIndex];

        // Record decision with metadata
        const decisionRecord = {
            item_id: item.item_id,
            decision: decision,
            participant_id: assignedParticipantId || identifiedCluster.participantId,
            timestamp: new Date().toISOString(),
            phase: 'cluster_confirm',
            cluster_id: identifiedCluster.clusterId,
            // Include training quality and reassignment info from metadata
            training_quality: metadata.trainingQuality ?? null,
            reassigned_from: metadata.reassignedFrom || null,
            reassigned_from_name: metadata.reassignedFromName || null,
            reassigned_to_name: metadata.reassignedToName || null
        };

        const newDecisions = [...decisions, decisionRecord];
        setDecisions(newDecisions);

        // Save immediately
        saveDecisionToServer(decisionRecord);

        // Add to undo stack (include identifiedCluster for restoration)
        setUndoStack([...undoStack, {
            phase: 'unknown_clusters',
            mode: 'confirm',
            clusterIndex: currentClusterIndex,
            clusterItemIndex: currentClusterItemIndex,
            decision: decisionRecord,
            identifiedCluster: identifiedCluster  // Save for undo restoration
        }]);

        // Increment items validated
        const newItemsValidated = itemsValidatedInSession + 1;
        setItemsValidatedInSession(newItemsValidated);

        // Move to next cluster item
        moveToNextClusterItem();
    };

    // Save a single decision immediately
    const saveDecisionToServer = useCallback(async (decisionRecord) => {
        try {
            const response = await fetch('/api/save-decision', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(decisionRecord)
            });
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }
        } catch (error) {
            console.error('Error saving decision:', error);
            if (toast.current) {
                toast.current.show({
                    severity: 'error',
                    summary: 'Save Failed',
                    detail: 'Decision may not have been saved. Check connection.',
                    life: 5000
                });
            }
        }
    }, []);

    // Remove a decision from server (for undo)
    const removeDecisionFromServer = useCallback(async (itemId) => {
        try {
            const response = await fetch('/api/remove-decision', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item_id: itemId })
            });
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }
        } catch (error) {
            console.error('Error removing decision:', error);
            if (toast.current) {
                toast.current.show({
                    severity: 'error',
                    summary: 'Undo Failed',
                    detail: 'Could not remove decision from server.',
                    life: 5000
                });
            }
        }
    }, []);

    // Check if an item has already been labeled
    const isItemLabeled = useCallback((itemId) => {
        return decisions.some(d => d.item_id === itemId);
    }, [decisions]);

    // Get decision for an item if it exists
    const getItemDecision = useCallback((itemId) => {
        return decisions.find(d => d.item_id === itemId);
    }, [decisions]);

    // Navigate to next item without making a decision
    const navigateNext = useCallback(() => {
        if (!queue || currentPhase !== 'known_matches') return;

        const participant = queue.participants[currentParticipantIndex];
        if (!participant) return;

        // Move within current participant
        if (currentItemIndex + 1 < participant.items.length) {
            setCurrentItemIndex(currentItemIndex + 1);
        }
        // Move to next participant
        else if (currentParticipantIndex + 1 < queue.participants.length) {
            setCurrentParticipantIndex(currentParticipantIndex + 1);
            setCurrentItemIndex(0);
        }
    }, [queue, currentPhase, currentParticipantIndex, currentItemIndex]);

    // Navigate to previous item without making a decision
    const navigatePrev = useCallback(() => {
        if (!queue || currentPhase !== 'known_matches') return;

        // Move within current participant
        if (currentItemIndex > 0) {
            setCurrentItemIndex(currentItemIndex - 1);
        }
        // Move to previous participant
        else if (currentParticipantIndex > 0) {
            const prevParticipant = queue.participants[currentParticipantIndex - 1];
            setCurrentParticipantIndex(currentParticipantIndex - 1);
            setCurrentItemIndex(prevParticipant.items.length - 1);
        }
    }, [queue, currentPhase, currentParticipantIndex, currentItemIndex]);

    // Navigation for cluster items
    const navigateClusterNext = useCallback(() => {
        if (!identifiedCluster || clusterMode !== 'confirm') return;
        if (currentClusterItemIndex + 1 < identifiedCluster.items.length) {
            setCurrentClusterItemIndex(currentClusterItemIndex + 1);
        }
    }, [identifiedCluster, clusterMode, currentClusterItemIndex]);

    const navigateClusterPrev = useCallback(() => {
        if (!identifiedCluster || clusterMode !== 'confirm') return;
        if (currentClusterItemIndex > 0) {
            setCurrentClusterItemIndex(currentClusterItemIndex - 1);
        }
    }, [identifiedCluster, clusterMode, currentClusterItemIndex]);

    // Skip a single cluster item (mark as skipped, move to next)
    const skipClusterItem = useCallback(() => {
        if (!identifiedCluster || clusterMode !== 'confirm') return;

        const item = identifiedCluster.items[currentClusterItemIndex];
        if (!item) return;

        // Record as skipped
        const decisionRecord = {
            item_id: item.item_id,
            decision: 'skipped',
            participant_id: null,
            timestamp: new Date().toISOString(),
            phase: 'cluster_confirm',
            cluster_id: identifiedCluster.clusterId,
            training_quality: null,
            reassigned_from: null,
            reassigned_from_name: null,
            reassigned_to_name: null
        };

        setDecisions(prev => [...prev, decisionRecord]);
        saveDecisionToServer(decisionRecord);

        // Move to next item in cluster
        if (currentClusterItemIndex + 1 < identifiedCluster.items.length) {
            setCurrentClusterItemIndex(currentClusterItemIndex + 1);
        } else {
            // All items done, move to next cluster
            if (queue && queue.unknown_clusters && currentClusterIndex + 1 < queue.unknown_clusters.length) {
                setCurrentClusterIndex(currentClusterIndex + 1);
                setClusterMode('identify');
                setIdentifiedCluster(null);
                setCurrentClusterItemIndex(0);
            } else {
                // All clusters done
                setCurrentClusterIndex(queue?.unknown_clusters?.length || 0);
            }
        }
    }, [identifiedCluster, clusterMode, currentClusterItemIndex, currentClusterIndex, queue, saveDecisionToServer]);

    const moveToNextKnownItem = () => {
        if (!queue) return;

        const participant = queue.participants[currentParticipantIndex];

        // Check if more items in current participant
        if (currentItemIndex + 1 < participant.items.length) {
            setCurrentItemIndex(currentItemIndex + 1);
        }
        // Move to next participant
        else if (currentParticipantIndex + 1 < queue.participants.length) {
            setCurrentParticipantIndex(currentParticipantIndex + 1);
            setCurrentItemIndex(0);

            if (toast.current) {
                const nextParticipant = queue.participants[currentParticipantIndex + 1];
                toast.current.show({
                    severity: 'info',
                    summary: 'Next Participant',
                    detail: `Now validating: ${nextParticipant.participant_name}`,
                    life: 3000
                });
            }
        }
        // Phase 1 complete - move to Phase 2
        else {
            if (queue.unknown_clusters && queue.unknown_clusters.length > 0) {
                setCurrentPhase('unknown_clusters');
                setCurrentClusterIndex(0);
                setClusterMode('identify');
                if (toast.current) {
                    toast.current.show({
                        severity: 'info',
                        summary: 'Phase 2: Unknown Speakers',
                        detail: `Now identifying ${queue.unknown_clusters.length} clusters of unknown speakers`,
                        life: 4000
                    });
                }
            } else {
                // All done
                setCurrentParticipantIndex(queue.participants.length);
            }
        }
    };

    const moveToNextClusterItem = () => {
        if (!identifiedCluster) return;

        // Check if more items in current cluster
        if (currentClusterItemIndex + 1 < identifiedCluster.items.length) {
            setCurrentClusterItemIndex(currentClusterItemIndex + 1);
        }
        // Move to next cluster
        else {
            moveToNextCluster();
        }
    };

    const moveToNextCluster = () => {
        if (!queue || !queue.unknown_clusters) return;

        if (currentClusterIndex + 1 < queue.unknown_clusters.length) {
            setCurrentClusterIndex(currentClusterIndex + 1);
            setClusterMode('identify');
            setIdentifiedCluster(null);
            setCurrentClusterItemIndex(0);
        } else {
            // All clusters done
            setCurrentClusterIndex(queue.unknown_clusters.length);
        }
    };

    // Handle cluster identification
    const handleClusterIdentify = async (clusterId, participantId, participantName) => {
        try {
            const response = await fetch('/api/identify-cluster', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cluster_id: clusterId,
                    participant_id: participantId,
                    participant_name: participantName
                })
            });
            const result = await response.json();

            if (result.success) {
                // Refresh participants list in case a new one was created
                loadParticipants();

                // Set up for confirmation phase
                setIdentifiedCluster({
                    clusterId: clusterId,
                    participantId: participantId,
                    participantName: participantName,
                    items: result.items
                });
                setClusterMode('confirm');
                setCurrentClusterItemIndex(0);

                if (toast.current) {
                    toast.current.show({
                        severity: 'success',
                        summary: 'Cluster Identified',
                        detail: `Now confirm ${result.items.length} speakers as ${participantName}`,
                        life: 3000
                    });
                }
            }
        } catch (error) {
            console.error('Error identifying cluster:', error);
            if (toast.current) {
                toast.current.show({
                    severity: 'error',
                    summary: 'Error',
                    detail: 'Failed to identify cluster',
                    life: 5000
                });
            }
        }
    };

    // Handle cluster skip
    const handleClusterSkip = (clusterId) => {
        moveToNextCluster();
    };

    const handleUndo = useCallback(() => {
        if (undoStack.length === 0) return;

        const lastAction = undoStack[undoStack.length - 1];

        // Remove from server first
        removeDecisionFromServer(lastAction.decision.item_id);

        // Remove last decision from local state
        setDecisions(prev => prev.slice(0, -1));
        setUndoStack(prev => prev.slice(0, -1));

        // Restore position based on phase
        if (lastAction.phase === 'known_matches') {
            setCurrentPhase('known_matches');
            setCurrentParticipantIndex(lastAction.participantIndex);
            setCurrentItemIndex(lastAction.itemIndex);
        } else if (lastAction.phase === 'unknown_clusters') {
            setCurrentPhase('unknown_clusters');
            setCurrentClusterIndex(lastAction.clusterIndex);
            if (lastAction.mode === 'confirm') {
                setClusterMode('confirm');
                setCurrentClusterItemIndex(lastAction.clusterItemIndex);
                // Restore identifiedCluster state
                if (lastAction.identifiedCluster) {
                    setIdentifiedCluster(lastAction.identifiedCluster);
                }
            }
        }

        setItemsValidatedInSession(prev => Math.max(0, prev - 1));

        if (toast.current) {
            toast.current.show({
                severity: 'info',
                summary: 'Undone',
                detail: 'Last decision removed',
                life: 2000
            });
        }
    }, [undoStack, removeDecisionFromServer]);

    // Keyboard shortcuts for undo and navigation
    useEffect(() => {
        const handleKeyPress = (e) => {
            // Ignore if typing in input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            // Ctrl+Z for undo
            if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
                e.preventDefault();
                handleUndo();
            }
            // [ for previous, ] for next (browse without labeling)
            else if (e.key === '[') {
                e.preventDefault();
                if (currentPhase === 'known_matches') {
                    navigatePrev();
                } else if (currentPhase === 'unknown_clusters' && clusterMode === 'confirm') {
                    navigateClusterPrev();
                }
            }
            else if (e.key === ']') {
                e.preventDefault();
                if (currentPhase === 'known_matches') {
                    navigateNext();
                } else if (currentPhase === 'unknown_clusters' && clusterMode === 'confirm') {
                    navigateClusterNext();
                }
            }
            // X to skip current clip (in cluster confirm mode)
            else if (e.key.toLowerCase() === 'x' && currentPhase === 'unknown_clusters' && clusterMode === 'confirm') {
                e.preventDefault();
                skipClusterItem();
            }
        };

        window.addEventListener('keydown', handleKeyPress);
        return () => window.removeEventListener('keydown', handleKeyPress);
    }, [handleUndo, navigatePrev, navigateNext, navigateClusterPrev, navigateClusterNext, skipClusterItem, currentPhase, clusterMode]);

    // Calculate overall progress
    const calculateOverallProgress = () => {
        if (!queue) return { completed: 0, total: 0 };

        const total = (queue.total_items || 0) + (queue.total_cluster_items || 0);
        return { completed: decisions.length, total };
    };

    const { completed: overallCompleted, total: overallTotal } = calculateOverallProgress();

    // Loading screen
    if (loading) {
        return (
            <div className="loading-screen">
                <ProgressSpinner style={{ width: '50px', height: '50px' }} />
                <h2>Loading validation queue...</h2>
            </div>
        );
    }

    // No items to validate - check that participants actually have items
    const hasKnownMatches = queue && queue.participants && queue.participants.some(p => p.items && p.items.length > 0);
    const hasClusters = queue && queue.unknown_clusters && queue.unknown_clusters.length > 0;

    if (!hasKnownMatches && !hasClusters) {
        return (
            <div className="loading-screen">
                <Icon name="CheckCircle2" size={64} color="#28a745" />
                <h2>No items to validate</h2>
                <p style={{ color: '#6c757d', marginTop: '1rem' }}>
                    All speaker identifications are complete!
                </p>
                <Button
                    label="Reload Queue"
                    icon="pi pi-refresh"
                    onClick={() => loadQueue()}
                    style={{ marginTop: '2rem' }}
                />
            </div>
        );
    }

    // Session complete
    const knownMatchesDone = !hasKnownMatches || currentParticipantIndex >= queue.participants.length;
    const clustersDone = !hasClusters || currentClusterIndex >= queue.unknown_clusters.length;

    if (knownMatchesDone && clustersDone) {
        return (
            <div className="loading-screen session-complete">
                <Icon name="PartyPopper" size={80} color="#28a745" />
                <h1 style={{ marginTop: '2rem' }}>Session Complete!</h1>
                <p style={{ fontSize: '1.25rem', color: '#6c757d', marginTop: '1rem' }}>
                    You validated {decisions.length} items
                </p>
                <div style={{ marginTop: '2rem' }}>
                    <Button
                        label="View Summary"
                        icon="pi pi-chart-bar"
                        size="large"
                        onClick={() => {
                            console.log('Decisions:', decisions);
                        }}
                        style={{ marginRight: '1rem' }}
                    />
                    <Button
                        label="Start New Session"
                        icon="pi pi-refresh"
                        size="large"
                        severity="secondary"
                        onClick={() => {
                            setCurrentParticipantIndex(0);
                            setCurrentItemIndex(0);
                            setCurrentClusterIndex(0);
                            setClusterMode('identify');
                            setIdentifiedCluster(null);
                            setCurrentPhase('known_matches');
                            loadQueue();
                        }}
                    />
                </div>
            </div>
        );
    }

    // Render based on current phase
    const renderPhaseContent = () => {
        if (currentPhase === 'known_matches' && hasKnownMatches && currentParticipantIndex < queue.participants.length) {
            let participantIdx = currentParticipantIndex;
            let currentParticipant = queue.participants[participantIdx];

            // Skip participants with no items (already validated)
            while ((!currentParticipant || !currentParticipant.items || currentParticipant.items.length === 0)
                   && participantIdx < queue.participants.length) {
                participantIdx++;
                currentParticipant = queue.participants[participantIdx];
            }

            // If we skipped participants, update state
            if (participantIdx !== currentParticipantIndex) {
                if (participantIdx < queue.participants.length) {
                    setTimeout(() => {
                        setCurrentParticipantIndex(participantIdx);
                        setCurrentItemIndex(0);
                    }, 0);
                    return <div className="loading-screen"><p>Loading next participant...</p></div>;
                } else {
                    // No more participants with items - move to clusters or complete
                    setTimeout(() => {
                        setCurrentParticipantIndex(queue.participants.length);
                    }, 0);
                    return <div className="loading-screen"><p>Moving to next phase...</p></div>;
                }
            }

            const currentItem = currentParticipant.items[currentItemIndex];

            // Guard against item index out of bounds
            if (!currentItem) {
                if (currentItemIndex >= currentParticipant.items.length) {
                    // Move to next participant
                    setTimeout(() => {
                        setCurrentParticipantIndex(participantIdx + 1);
                        setCurrentItemIndex(0);
                    }, 0);
                }
                return <div className="loading-screen"><p>Loading next item...</p></div>;
            }

            return (
                <>
                    <ProgressHeader
                        currentParticipant={currentParticipant.participant_name}
                        participantIndex={currentParticipantIndex}
                        totalParticipants={queue.participants.length}
                        itemIndex={currentItemIndex}
                        totalItemsInParticipant={currentParticipant.items.length}
                        overallProgress={overallCompleted}
                        overallTotal={overallTotal}
                        phase="known"
                    />

                    <div className="validation-container">
                        <div style={{ position: 'relative', width: '100%', maxWidth: '700px' }}>
                            {/* Navigation and action bar */}
                            <div className="validation-nav-bar">
                                <div className="nav-buttons">
                                    <Button
                                        icon="pi pi-chevron-left"
                                        severity="secondary"
                                        outlined
                                        size="small"
                                        onClick={navigatePrev}
                                        disabled={currentParticipantIndex === 0 && currentItemIndex === 0}
                                        tooltip="Previous ([)"
                                        tooltipOptions={{ position: 'top' }}
                                    />
                                    <Button
                                        icon="pi pi-chevron-right"
                                        severity="secondary"
                                        outlined
                                        size="small"
                                        onClick={navigateNext}
                                        tooltip="Next (])"
                                        tooltipOptions={{ position: 'top' }}
                                    />
                                </div>

                                {/* Labeled indicator */}
                                {isItemLabeled(currentItem.item_id) && (
                                    <div className="labeled-indicator">
                                        <Icon name="CheckCircle" size={16} />
                                        <span>Already labeled: {getItemDecision(currentItem.item_id)?.decision}</span>
                                    </div>
                                )}

                                {undoStack.length > 0 && (
                                    <Button
                                        label="Undo"
                                        icon="pi pi-undo"
                                        severity="secondary"
                                        outlined
                                        size="small"
                                        onClick={handleUndo}
                                    />
                                )}
                            </div>

                            <ValidationCard
                                item={currentItem}
                                participantName={currentParticipant.participant_name}
                                participantId={currentParticipant.participant_id}
                                onDecision={handleDecision}
                                existingParticipants={existingParticipants}
                                onCreateParticipant={handleCreateParticipant}
                            />
                        </div>
                    </div>
                </>
            );
        }

        if (currentPhase === 'unknown_clusters' && hasClusters && currentClusterIndex < queue.unknown_clusters.length) {
            const currentCluster = queue.unknown_clusters[currentClusterIndex];

            if (clusterMode === 'identify') {
                return (
                    <>
                        <ProgressHeader
                            currentParticipant={`Cluster ${currentClusterIndex + 1}`}
                            participantIndex={currentClusterIndex}
                            totalParticipants={queue.unknown_clusters.length}
                            itemIndex={0}
                            totalItemsInParticipant={currentCluster.size}
                            overallProgress={overallCompleted}
                            overallTotal={overallTotal}
                            phase="unknown"
                        />

                        <div className="validation-container">
                            <div style={{ position: 'relative', width: '100%', maxWidth: '700px' }}>
                                {undoStack.length > 0 && (
                                    <div style={{ position: 'absolute', top: '-60px', right: '0' }}>
                                        <Button
                                            label="Undo"
                                            icon="pi pi-undo"
                                            severity="secondary"
                                            outlined
                                            size="small"
                                            onClick={handleUndo}
                                        />
                                    </div>
                                )}

                                <IdentificationCard
                                    cluster={currentCluster}
                                    existingParticipants={existingParticipants}
                                    onIdentify={handleClusterIdentify}
                                    onSkip={handleClusterSkip}
                                />
                            </div>
                        </div>
                    </>
                );
            }

            if (clusterMode === 'confirm' && identifiedCluster) {
                const currentItem = identifiedCluster.items[currentClusterItemIndex];

                return (
                    <>
                        <ProgressHeader
                            currentParticipant={identifiedCluster.participantName}
                            participantIndex={currentClusterIndex}
                            totalParticipants={queue.unknown_clusters.length}
                            itemIndex={currentClusterItemIndex}
                            totalItemsInParticipant={identifiedCluster.items.length}
                            overallProgress={overallCompleted}
                            overallTotal={overallTotal}
                            phase="unknown"
                            subPhase="confirm"
                        />

                        <div className="validation-container">
                            <div style={{ position: 'relative', width: '100%', maxWidth: '700px' }}>
                                {/* Navigation and action bar */}
                                <div className="validation-nav-bar">
                                    <div className="nav-buttons">
                                        <Button
                                            icon="pi pi-chevron-left"
                                            severity="secondary"
                                            outlined
                                            size="small"
                                            onClick={navigateClusterPrev}
                                            disabled={currentClusterItemIndex === 0}
                                            tooltip="Previous clip ([)"
                                            tooltipOptions={{ position: 'top' }}
                                        />
                                        <Button
                                            icon="pi pi-chevron-right"
                                            severity="secondary"
                                            outlined
                                            size="small"
                                            onClick={navigateClusterNext}
                                            disabled={currentClusterItemIndex >= identifiedCluster.items.length - 1}
                                            tooltip="Next clip (])"
                                            tooltipOptions={{ position: 'top' }}
                                        />
                                    </div>

                                    <Button
                                        label="Skip Clip"
                                        icon="pi pi-forward"
                                        severity="warning"
                                        outlined
                                        size="small"
                                        onClick={skipClusterItem}
                                        tooltip="Skip this clip only (X)"
                                        tooltipOptions={{ position: 'top' }}
                                    />

                                    {undoStack.length > 0 && (
                                        <Button
                                            label="Undo"
                                            icon="pi pi-undo"
                                            severity="secondary"
                                            outlined
                                            size="small"
                                            onClick={handleUndo}
                                        />
                                    )}
                                </div>

                                <ValidationCard
                                    item={currentItem}
                                    participantName={identifiedCluster.participantName}
                                    participantId={identifiedCluster.participantId}
                                    onDecision={handleClusterDecision}
                                    existingParticipants={existingParticipants}
                                    onCreateParticipant={handleCreateParticipant}
                                />
                            </div>
                        </div>
                    </>
                );
            }
        }

        return null;
    };

    return (
        <>
            <Toast ref={toast} position="top-right" />

            {renderPhaseContent()}

            {/* Break reminder dialog */}
            <Dialog
                header="Take a Break?"
                visible={showBreakReminder}
                style={{ width: '450px' }}
                onHide={() => setShowBreakReminder(false)}
                footer={
                    <div>
                        <Button
                            label="Continue"
                            icon="pi pi-arrow-right"
                            onClick={() => setShowBreakReminder(false)}
                            autoFocus
                        />
                        <Button
                            label="Take a Break"
                            icon="pi pi-pause"
                            severity="secondary"
                            onClick={() => {
                                setShowBreakReminder(false);
                                if (toast.current) {
                                    toast.current.show({
                                        severity: 'success',
                                        summary: 'Progress Saved',
                                        detail: 'Your decisions are saved. Close the browser anytime.',
                                        life: 5000
                                    });
                                }
                            }}
                        />
                    </div>
                }
            >
                <div style={{ textAlign: 'center', padding: '1rem' }}>
                    <Icon name="Coffee" size={48} color="#6c757d" />
                    <p style={{ marginTop: '1rem', fontSize: '1.1rem' }}>
                        You've validated {itemsValidatedInSession} items.
                    </p>
                    <p style={{ marginTop: '0.5rem', color: '#6c757d' }}>
                        Consider taking a short break to stay fresh!
                    </p>
                </div>
            </Dialog>
        </>
    );
};
