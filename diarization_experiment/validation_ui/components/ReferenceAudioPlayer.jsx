// Reference Audio Player Component
const { useState, useEffect } = React;
const { Button } = PrimeReactBundle;
const { Icon, AudioPlayer } = ValidationApp;

ValidationApp.ReferenceAudioPlayer = function ReferenceAudioPlayer({ participantId, participantName }) {
    const [samples, setSamples] = useState([]);
    const [currentSampleIndex, setCurrentSampleIndex] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [loading, setLoading] = useState(false);

    // Load reference audio samples
    useEffect(() => {
        if (!participantId) {
            setSamples([]);
            return;
        }

        setLoading(true);
        fetch(`/api/reference-audio/${participantId}`)
            .then(res => res.json())
            .then(data => {
                setSamples(data.samples || []);
                setCurrentSampleIndex(0);
            })
            .catch(err => {
                console.error('Error loading reference audio:', err);
                setSamples([]);
            })
            .finally(() => {
                setLoading(false);
            });
    }, [participantId]);

    const playNextSample = () => {
        if (samples.length === 0) return;
        setCurrentSampleIndex((prev) => (prev + 1) % samples.length);
    };

    const handleKeyPress = (e) => {
        if (e.key === 'r' || e.key === 'R') {
            if (samples.length > 0) {
                setIsPlaying(true);
                setTimeout(() => setIsPlaying(false), 100);
            }
        }
    };

    useEffect(() => {
        window.addEventListener('keydown', handleKeyPress);
        return () => window.removeEventListener('keydown', handleKeyPress);
    }, [samples]);

    if (loading) {
        return (
            <div className="reference-audio-section">
                <div style={{ textAlign: 'center', padding: '1rem' }}>
                    <i className="pi pi-spin pi-spinner" style={{ fontSize: '1.5rem' }} />
                    <p style={{ marginTop: '0.5rem', fontSize: '14px' }}>Loading reference audio...</p>
                </div>
            </div>
        );
    }

    if (samples.length === 0) {
        return null;
    }

    const currentSample = samples[currentSampleIndex];

    return (
        <div className="reference-audio-section">
            <div className="reference-header">
                <div className="reference-title">
                    <Icon name="Headphones" size={18} />
                    <span>Reference Audio for {participantName}</span>
                </div>
                <span className="reference-sample-indicator">
                    {currentSampleIndex + 1} / {samples.length}
                </span>
            </div>

            <p className="reference-recording-title">
                {currentSample.recording_title}
            </p>

            <div className="reference-player-wrapper">
                <AudioPlayer audioInfo={currentSample.audio} autoFocus={false} onPlayComplete={playNextSample} />
            </div>

            {samples.length > 1 && (
                <div className="reference-cycle-hint">
                    Press <span className="keyboard-hint">R</span> to hear another sample
                </div>
            )}
        </div>
    );
};
