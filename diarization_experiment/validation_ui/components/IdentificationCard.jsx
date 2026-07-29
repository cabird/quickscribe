// Identification Card Component - "Who is this?" flow for unknown speaker clusters
const { useState, useEffect, useRef, useCallback } = React;
const { Card, Button, InputText, Dropdown, Toast } = PrimeReactBundle;
const { Icon, AudioPlayer } = ValidationApp;

ValidationApp.IdentificationCard = function IdentificationCard({
    cluster,
    existingParticipants,
    onIdentify,
    onSkip
}) {
    const [selectedParticipant, setSelectedParticipant] = useState(null);
    const [newName, setNewName] = useState('');
    const [isCreatingNew, setIsCreatingNew] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [errorMessage, setErrorMessage] = useState(null);
    const [sampleIndex, setSampleIndex] = useState(0); // Which sample to show
    const inputRef = useRef(null);
    const toastRef = useRef(null);

    // Focus input only when in "create new" mode
    useEffect(() => {
        if (isCreatingNew && inputRef.current) {
            setTimeout(() => inputRef.current.focus(), 100);
        }
    }, [isCreatingNew, cluster?.cluster_id]);

    // Reset state when cluster changes
    useEffect(() => {
        setSelectedParticipant(null);
        setNewName('');
        setIsCreatingNew(false);
        setIsSubmitting(false);
        setErrorMessage(null);
        setSampleIndex(0);
    }, [cluster?.cluster_id]);

    const handleSubmit = useCallback(async () => {
        if (isSubmitting) return;
        setErrorMessage(null);

        if (isCreatingNew && newName.trim()) {
            // Create new participant
            setIsSubmitting(true);
            try {
                const response = await fetch('/api/create-participant', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ displayName: newName.trim() })
                });
                const result = await response.json();
                if (result.success) {
                    onIdentify(cluster.cluster_id, result.participant.id, result.participant.displayName);
                } else {
                    console.error('Failed to create participant:', result.error);
                    setErrorMessage(result.error || 'Failed to create participant');
                    if (toastRef.current) {
                        toastRef.current.show({
                            severity: 'error',
                            summary: 'Error',
                            detail: result.error || 'Failed to create participant',
                            life: 5000
                        });
                    }
                    setIsSubmitting(false);
                }
            } catch (error) {
                console.error('Error creating participant:', error);
                setErrorMessage('Network error. Please try again.');
                if (toastRef.current) {
                    toastRef.current.show({
                        severity: 'error',
                        summary: 'Network Error',
                        detail: 'Failed to create participant. Check your connection.',
                        life: 5000
                    });
                }
                setIsSubmitting(false);
            }
        } else if (selectedParticipant) {
            // Use existing participant
            onIdentify(cluster.cluster_id, selectedParticipant.id, selectedParticipant.displayName);
        }
    }, [isCreatingNew, newName, selectedParticipant, cluster, onIdentify, isSubmitting]);

    const handleKeyPress = useCallback((e) => {
        if (e.key === 'Enter' && (newName.trim() || selectedParticipant)) {
            handleSubmit();
        }
    }, [handleSubmit, newName, selectedParticipant]);

    // Navigation between samples
    const totalSamples = cluster?.items?.length || 1;
    const nextSample = useCallback(() => {
        if (sampleIndex + 1 < totalSamples) {
            setSampleIndex(sampleIndex + 1);
        }
    }, [sampleIndex, totalSamples]);

    const prevSample = useCallback(() => {
        if (sampleIndex > 0) {
            setSampleIndex(sampleIndex - 1);
        }
    }, [sampleIndex]);

    // Keyboard shortcuts for skip and sample navigation
    const clusterId = cluster?.cluster_id;
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (!clusterId) return;  // Guard against null cluster
            if (e.target.tagName === 'INPUT') return;
            if (e.key.toLowerCase() === 's' || e.key === 'ArrowDown') {
                onSkip(clusterId);
            }
            // [ and ] for sample navigation
            else if (e.key === '[') {
                e.preventDefault();
                prevSample();
            }
            else if (e.key === ']') {
                e.preventDefault();
                nextSample();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [onSkip, clusterId, prevSample, nextSample]);

    if (!cluster) {
        return (
            <div className="identification-card">
                <Card>
                    <div style={{ textAlign: 'center', padding: '2rem' }}>
                        <p>Loading...</p>
                    </div>
                </Card>
            </div>
        );
    }

    // Get current sample - try items array first, fall back to representative
    const currentSample = cluster.items?.[sampleIndex] || cluster.representative;
    const hasMutipleSamples = totalSamples > 1;

    return (
        <div className="identification-card">
            <Toast ref={toastRef} position="top-right" />
            <Card>
                {/* Cluster Info */}
                <div className="cluster-badge">
                    <Icon name="Users" size={16} />
                    <span>Appears in {cluster.size} recording{cluster.size > 1 ? 's' : ''}</span>
                </div>

                {/* Main Question */}
                <div className="main-question">
                    <h1>Who is this?</h1>
                    <p className="subtitle">Listen to identify this unknown speaker</p>
                </div>

                {/* Sample Navigation */}
                {hasMutipleSamples && (
                    <div className="sample-navigation">
                        <Button
                            icon="pi pi-chevron-left"
                            severity="secondary"
                            outlined
                            size="small"
                            onClick={prevSample}
                            disabled={sampleIndex === 0}
                            tooltip="Previous sample ([)"
                            tooltipOptions={{ position: 'top' }}
                        />
                        <span className="sample-indicator">
                            Sample {sampleIndex + 1} of {totalSamples}
                        </span>
                        <Button
                            icon="pi pi-chevron-right"
                            severity="secondary"
                            outlined
                            size="small"
                            onClick={nextSample}
                            disabled={sampleIndex >= totalSamples - 1}
                            tooltip="Next sample (])"
                            tooltipOptions={{ position: 'top' }}
                        />
                    </div>
                )}

                {/* Context Info */}
                <div className="context-info">
                    <span>
                        <Icon name="FileAudio" size={14} />
                        {currentSample.recording_title}
                    </span>
                    <span className="separator">|</span>
                    <span>
                        <Icon name="MessageSquare" size={14} />
                        {currentSample.segment_count} segments
                    </span>
                    <span className="separator">|</span>
                    <span>
                        <Icon name="Clock" size={14} />
                        {Math.round(currentSample.total_duration)}s
                    </span>
                </div>

                {/* Audio Player */}
                <AudioPlayer audioInfo={currentSample.audio} />

                {/* Identification Form */}
                <div className="identification-form">
                    {!isCreatingNew ? (
                        <>
                            <div className="form-group">
                                <label>Select existing person:</label>
                                <Dropdown
                                    value={selectedParticipant}
                                    options={existingParticipants}
                                    onChange={(e) => setSelectedParticipant(e.value)}
                                    optionLabel="displayName"
                                    placeholder="Choose a person..."
                                    filter
                                    filterPlaceholder="Search..."
                                    className="w-full"
                                    style={{ width: '100%' }}
                                />
                            </div>
                            <div className="form-divider">
                                <span>or</span>
                            </div>
                            <Button
                                label="Add New Person"
                                icon="pi pi-plus"
                                severity="secondary"
                                outlined
                                onClick={() => setIsCreatingNew(true)}
                                style={{ width: '100%' }}
                            />
                        </>
                    ) : (
                        <>
                            <div className="form-group">
                                <label>Enter name:</label>
                                <InputText
                                    ref={inputRef}
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    onKeyPress={handleKeyPress}
                                    placeholder="e.g., John Smith"
                                    className="w-full"
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
                                    setIsCreatingNew(false);
                                    setNewName('');
                                }}
                                style={{ marginTop: '0.5rem' }}
                            />
                        </>
                    )}
                </div>

                {/* Action Buttons */}
                <div className="action-buttons">
                    <Button
                        label="Skip Cluster"
                        icon="pi pi-arrow-down"
                        severity="secondary"
                        size="large"
                        outlined
                        onClick={() => onSkip(cluster.cluster_id)}
                        style={{ minWidth: '140px' }}
                    />
                    <Button
                        label={isCreatingNew ? "Create & Identify" : "Identify"}
                        icon="pi pi-check"
                        severity="success"
                        size="large"
                        onClick={handleSubmit}
                        disabled={isSubmitting || (!selectedParticipant && !newName.trim())}
                        loading={isSubmitting}
                        style={{ minWidth: '180px' }}
                    />
                </div>

                {/* Keyboard Hints */}
                <div className="keyboard-hints-row">
                    {hasMutipleSamples && (
                        <span><span className="keyboard-hint">[</span> <span className="keyboard-hint">]</span> Switch sample</span>
                    )}
                    <span><span className="keyboard-hint">S</span> Skip</span>
                    <span><span className="keyboard-hint">Enter</span> Confirm</span>
                </div>
            </Card>
        </div>
    );
};
