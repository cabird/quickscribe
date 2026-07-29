// Validation Card Component - Enhanced with training quality and reassignment
const { useState, useEffect, useRef, useCallback } = React;
const { Card, Button, Tag, Dropdown, Dialog } = PrimeReactBundle;
const { Icon, AudioPlayer, ReferenceAudioPlayer } = ValidationApp;

ValidationApp.ValidationCard = function ValidationCard({
    item,
    participantName,
    participantId,
    onDecision,
    showFeedback = true,
    existingParticipants = [],
    onCreateParticipant
}) {
    const [flashClass, setFlashClass] = useState('');
    const [showReassignDialog, setShowReassignDialog] = useState(false);
    const [selectedParticipant, setSelectedParticipant] = useState(null);
    const [newParticipantName, setNewParticipantName] = useState('');
    const [isCreatingParticipant, setIsCreatingParticipant] = useState(false);
    const [reassignTrainingQuality, setReassignTrainingQuality] = useState(true);
    const [createError, setCreateError] = useState(null);
    const cardRef = useRef(null);

    // Reset state when item changes
    useEffect(() => {
        setShowReassignDialog(false);
        setSelectedParticipant(null);
        setNewParticipantName('');
        setIsCreatingParticipant(false);
        setReassignTrainingQuality(true);
        setCreateError(null);
    }, [item?.item_id]);

    // All hooks must be called before any early returns (React rules of hooks)
    const handleConfirmTraining = useCallback(() => {
        if (!item) return;
        if (showFeedback) {
            setFlashClass('success-flash');
            setTimeout(() => setFlashClass(''), 300);
        }
        setTimeout(() => {
            onDecision('confirmed', participantId, { trainingQuality: true });
        }, showFeedback ? 200 : 0);
    }, [item, onDecision, participantId, showFeedback]);

    const handleConfirmNotTraining = useCallback(() => {
        if (!item) return;
        if (showFeedback) {
            setFlashClass('success-flash-dim');
            setTimeout(() => setFlashClass(''), 300);
        }
        setTimeout(() => {
            onDecision('confirmed', participantId, { trainingQuality: false });
        }, showFeedback ? 200 : 0);
    }, [item, onDecision, participantId, showFeedback]);

    const handleReject = useCallback(() => {
        if (!item) return;
        // Show reassign dialog instead of immediate reject
        setShowReassignDialog(true);
    }, [item]);

    const handleReassign = useCallback(async () => {
        if (!item) return;

        let targetParticipantId = null;
        let targetParticipantName = null;

        setCreateError(null);

        if (isCreatingParticipant && newParticipantName.trim()) {
            // Create new participant
            if (onCreateParticipant) {
                try {
                    const result = await onCreateParticipant(newParticipantName.trim());
                    if (result) {
                        targetParticipantId = result.id;
                        targetParticipantName = result.displayName;
                    } else {
                        setCreateError('Failed to create participant. Please try again.');
                        return;
                    }
                } catch (error) {
                    console.error('Error creating participant:', error);
                    setCreateError(`Error: ${error.message || 'Failed to create participant'}`);
                    return;
                }
            }
        } else if (selectedParticipant) {
            targetParticipantId = selectedParticipant.id;
            targetParticipantName = selectedParticipant.displayName;
        }

        if (!targetParticipantId) return;

        setShowReassignDialog(false);
        if (showFeedback) {
            setFlashClass('warning-flash');
            setTimeout(() => setFlashClass(''), 300);
        }
        setTimeout(() => {
            onDecision('reassigned', targetParticipantId, {
                trainingQuality: reassignTrainingQuality,
                reassignedFrom: participantId,
                reassignedFromName: participantName,
                reassignedToName: targetParticipantName
            });
        }, showFeedback ? 200 : 0);
    }, [item, selectedParticipant, newParticipantName, isCreatingParticipant, reassignTrainingQuality,
        onDecision, onCreateParticipant, participantId, participantName, showFeedback]);

    const handleSkipFromDialog = useCallback(() => {
        if (!item) return;
        setShowReassignDialog(false);
        if (showFeedback) {
            setFlashClass('error-flash');
            setTimeout(() => setFlashClass(''), 300);
        }
        setTimeout(() => {
            onDecision('rejected', null, { trainingQuality: false });
        }, showFeedback ? 200 : 0);
    }, [item, onDecision, showFeedback]);

    const handleSkip = useCallback(() => {
        if (!item) return;
        onDecision('skipped', null);
    }, [item, onDecision]);

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyPress = (e) => {
            // Ignore if typing in input or dialog is open
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            if (showReassignDialog) {
                if (e.key === 'Escape') {
                    setShowReassignDialog(false);
                }
                return;
            }

            switch (e.key.toLowerCase()) {
                case 'y':
                    if (e.shiftKey) {
                        handleConfirmNotTraining();
                    } else {
                        handleConfirmTraining();
                    }
                    break;
                case 'arrowright':
                    handleConfirmTraining();
                    break;
                case 'n':
                case 'arrowleft':
                    handleReject();
                    break;
                case 's':
                case 'arrowdown':
                    handleSkip();
                    break;
            }
        };

        window.addEventListener('keydown', handleKeyPress);
        return () => window.removeEventListener('keydown', handleKeyPress);
    }, [handleConfirmTraining, handleConfirmNotTraining, handleReject, handleSkip, showReassignDialog]);

    // Defensive: if item is undefined, show loading state (AFTER all hooks)
    if (!item) {
        return (
            <div className="validation-card">
                <Card>
                    <div style={{ textAlign: 'center', padding: '2rem' }}>
                        <p>Loading...</p>
                    </div>
                </Card>
            </div>
        );
    }

    const confidencePercent = (item.similarity * 100).toFixed(0);

    // Filter out current participant from reassign options
    const reassignOptions = existingParticipants.filter(p => p.id !== participantId);

    return (
        <div className="validation-card" ref={cardRef}>
            <Card className={flashClass}>
                {/* Reference Audio */}
                <ReferenceAudioPlayer
                    participantId={participantId}
                    participantName={participantName}
                />

                {/* Main Question */}
                <div className="main-question">
                    <h1>Is this</h1>
                    <span className="participant-name-large">{participantName}?</span>
                </div>

                {/* Context Info */}
                <div className="context-info">
                    <span>
                        <Icon name="FileAudio" size={14} />
                        {item.recording_title}
                    </span>
                    <span className="separator">|</span>
                    <span>
                        <Icon name="MessageSquare" size={14} />
                        {item.segment_count} segments
                    </span>
                    <span className="separator">|</span>
                    <span>
                        <Icon name="Clock" size={14} />
                        {Math.round(item.total_duration)}s
                    </span>
                </div>

                {/* Confidence Indicator */}
                <div className="confidence-section">
                    <div className="confidence-header">
                        <span className="confidence-label">Match Confidence</span>
                        <Tag
                            value={`${confidencePercent}%`}
                            severity={item.similarity >= 0.75 ? 'success' : item.similarity >= 0.5 ? 'warning' : 'danger'}
                        />
                    </div>
                    <div className="confidence-bar">
                        <div
                            className={`confidence-fill ${item.similarity >= 0.75 ? 'high' : item.similarity >= 0.5 ? 'medium' : 'low'}`}
                            style={{ width: `${confidencePercent}%` }}
                        />
                    </div>
                </div>

                {/* Audio Player */}
                <AudioPlayer audioInfo={item.audio} />

                {/* Action Buttons - Two rows */}
                <div className="action-buttons-container">
                    {/* Primary row: Yes options */}
                    <div className="action-buttons-row primary-row">
                        <Button
                            label="Yes - Training"
                            icon="pi pi-star"
                            severity="success"
                            size="large"
                            onClick={handleConfirmTraining}
                            className="btn-yes-training"
                            tooltip="Good quality audio for training (Y)"
                            tooltipOptions={{ position: 'top' }}
                        />
                        <Button
                            label="Yes - Not Training"
                            icon="pi pi-check"
                            severity="success"
                            size="large"
                            outlined
                            onClick={handleConfirmNotTraining}
                            className="btn-yes-not-training"
                            tooltip="Correct person but audio not suitable for training (Shift+Y)"
                            tooltipOptions={{ position: 'top' }}
                        />
                    </div>

                    {/* Secondary row: No/Skip options */}
                    <div className="action-buttons-row secondary-row">
                        <Button
                            label="Not This Person"
                            icon="pi pi-times"
                            severity="danger"
                            size="large"
                            outlined
                            onClick={handleReject}
                            className="btn-no"
                            tooltip="Wrong person - reassign or reject (N)"
                            tooltipOptions={{ position: 'top' }}
                        />
                        <Button
                            label="Skip"
                            icon="pi pi-arrow-down"
                            severity="secondary"
                            size="large"
                            outlined
                            onClick={handleSkip}
                            className="btn-skip"
                            tooltip="Skip for now (S)"
                            tooltipOptions={{ position: 'top' }}
                        />
                    </div>
                </div>

                {/* Keyboard Hints */}
                <div className="keyboard-hints-row">
                    <span><span className="keyboard-hint">Y</span> Yes (Training)</span>
                    <span><span className="keyboard-hint">Shift+Y</span> Yes (Not Training)</span>
                    <span><span className="keyboard-hint">N</span> Not This Person</span>
                    <span><span className="keyboard-hint">S</span> Skip</span>
                </div>
            </Card>

            {/* Reassign Dialog */}
            <Dialog
                header="Who is this speaker?"
                visible={showReassignDialog}
                style={{ width: '500px' }}
                onHide={() => { setShowReassignDialog(false); setCreateError(null); }}
                footer={
                    <div className="reassign-dialog-footer">
                        <Button
                            label="Cancel"
                            icon="pi pi-arrow-left"
                            severity="secondary"
                            text
                            onClick={() => { setShowReassignDialog(false); setCreateError(null); }}
                        />
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <Button
                                label="Just Reject"
                                icon="pi pi-times"
                                severity="danger"
                                outlined
                                onClick={handleSkipFromDialog}
                                tooltip="Mark as wrong person without specifying who"
                                tooltipOptions={{ position: 'top' }}
                            />
                            <Button
                                label="Reassign"
                                icon="pi pi-check"
                                severity="success"
                                onClick={handleReassign}
                                disabled={!selectedParticipant && (!isCreatingParticipant || !newParticipantName.trim())}
                            />
                        </div>
                    </div>
                }
            >
                <div className="reassign-dialog-content">
                    <p>
                        This is not <strong>{participantName}</strong>. Who is it?
                    </p>

                    {/* Error message */}
                    {createError && (
                        <div className="reassign-error-message">
                            <Icon name="AlertCircle" size={16} />
                            <span>{createError}</span>
                        </div>
                    )}

                    {!isCreatingParticipant ? (
                        <>
                            <div className="form-group">
                                <label>Select existing person:</label>
                                <Dropdown
                                    value={selectedParticipant}
                                    options={reassignOptions}
                                    onChange={(e) => setSelectedParticipant(e.value)}
                                    optionLabel="displayName"
                                    placeholder="Choose a person..."
                                    filter
                                    filterPlaceholder="Search..."
                                    style={{ width: '100%' }}
                                    showClear
                                />
                            </div>
                            <div className="form-divider">
                                <span>or</span>
                            </div>
                            <Button
                                label="Create New Person"
                                icon="pi pi-plus"
                                severity="secondary"
                                outlined
                                onClick={() => setIsCreatingParticipant(true)}
                                style={{ width: '100%' }}
                            />
                        </>
                    ) : (
                        <>
                            <div className="form-group">
                                <label>Enter name:</label>
                                <input
                                    type="text"
                                    value={newParticipantName}
                                    onChange={(e) => setNewParticipantName(e.target.value)}
                                    placeholder="e.g., John Smith"
                                    className="p-inputtext p-component"
                                    style={{ width: '100%' }}
                                    autoFocus
                                />
                            </div>
                            <Button
                                label="Back to Selection"
                                icon="pi pi-arrow-left"
                                severity="secondary"
                                text
                                onClick={() => {
                                    setIsCreatingParticipant(false);
                                    setNewParticipantName('');
                                    setCreateError(null);
                                }}
                            />
                        </>
                    )}

                    {/* Training quality checkbox */}
                    <div className="training-quality-option">
                        <label className="checkbox-label">
                            <input
                                type="checkbox"
                                checked={reassignTrainingQuality}
                                onChange={(e) => setReassignTrainingQuality(e.target.checked)}
                            />
                            <span>Good quality audio (use for training)</span>
                        </label>
                        <small>Uncheck if the audio is noisy or has overlapping speech</small>
                    </div>
                </div>
            </Dialog>
        </div>
    );
};
