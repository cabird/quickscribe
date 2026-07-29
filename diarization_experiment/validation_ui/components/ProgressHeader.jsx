// Progress Header Component
const { ProgressBar, Chip } = PrimeReactBundle;
const { Icon } = ValidationApp;

ValidationApp.ProgressHeader = function ProgressHeader({
    currentParticipant,
    participantIndex,
    totalParticipants,
    itemIndex,
    totalItemsInParticipant,
    overallProgress,
    overallTotal,
    phase = 'known',  // 'known' or 'unknown'
    subPhase = null   // 'confirm' for cluster confirmation
}) {
    const participantProgress = totalItemsInParticipant > 0
        ? ((itemIndex + 1) / totalItemsInParticipant) * 100
        : 0;

    const overallProgressPercent = overallTotal > 0
        ? (overallProgress / overallTotal) * 100
        : 0;

    const phaseLabel = phase === 'known'
        ? 'Known Speakers'
        : (subPhase === 'confirm' ? 'Confirming Cluster' : 'Unknown Speakers');

    const phaseIcon = phase === 'known' ? 'pi pi-user-check' : 'pi pi-users';

    return (
        <div className="progress-header">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--spacing-md)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)' }}>
                    <h2 style={{ margin: 0, fontSize: 'var(--font-size-2xl)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                        Speaker Validation
                    </h2>
                    <span className={`phase-badge ${phase === 'known' ? 'phase-known' : 'phase-unknown'}`}>
                        <i className={phaseIcon} style={{ fontSize: '0.75rem' }}></i>
                        {phaseLabel}
                    </span>
                </div>
                <Chip
                    label={`${overallProgress} / ${overallTotal} completed`}
                    icon="pi pi-check-circle"
                    style={{ background: 'var(--color-bg-subtle)', color: 'var(--color-primary)', fontWeight: 500 }}
                />
            </div>

            {currentParticipant && (
                <>
                    <div style={{ marginBottom: 'var(--spacing-sm)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--spacing-xs)' }}>
                            <span style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                                {currentParticipant}
                                <span style={{ fontWeight: 400, color: 'var(--color-text-muted)', marginLeft: 'var(--spacing-sm)' }}>
                                    ({participantIndex + 1} of {totalParticipants})
                                </span>
                            </span>
                            <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
                                {itemIndex + 1} / {totalItemsInParticipant}
                            </span>
                        </div>
                        <ProgressBar
                            value={participantProgress}
                            showValue={false}
                            style={{ height: '6px', borderRadius: '3px' }}
                        />
                    </div>

                    <div style={{ marginTop: 'var(--spacing-sm)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginBottom: 'var(--spacing-xs)' }}>
                            <span>Overall Progress</span>
                            <span style={{ fontVariantNumeric: 'tabular-nums' }}>{overallProgressPercent.toFixed(0)}%</span>
                        </div>
                        <ProgressBar
                            value={overallProgressPercent}
                            showValue={false}
                            style={{ height: '4px', borderRadius: '2px' }}
                            color="var(--color-success)"
                        />
                    </div>
                </>
            )}
        </div>
    );
};
