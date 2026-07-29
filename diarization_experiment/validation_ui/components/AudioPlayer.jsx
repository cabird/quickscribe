// Audio Player Component
const { useRef, useState, useEffect } = React;
const { Button } = PrimeReactBundle;
const { Icon } = ValidationApp;

ValidationApp.AudioPlayer = function AudioPlayer({ audioInfo, onPlayComplete, autoFocus = true }) {
    const audioRef = useRef(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);

    useEffect(() => {
        // Reset state when audioInfo changes
        setIsPlaying(false);
        setCurrentTime(0);
        setDuration(0);

        if (!audioInfo || !audioRef.current) return;

        const audio = audioRef.current;

        // Stop any current playback
        audio.pause();

        // Load the audio
        audio.src = audioInfo.url;
        audio.currentTime = audioInfo.start || 0;

        const handleLoadedMetadata = () => {
            setDuration((audioInfo.end || audio.duration) - (audioInfo.start || 0));
        };

        const handleTimeUpdate = () => {
            const elapsed = audio.currentTime - (audioInfo.start || 0);
            setCurrentTime(elapsed);

            // Stop at end time if specified
            if (audioInfo.end && audio.currentTime >= audioInfo.end) {
                audio.pause();
                setIsPlaying(false);
                setCurrentTime(0);
                if (onPlayComplete) {
                    onPlayComplete();
                }
            }
        };

        const handleEnded = () => {
            setIsPlaying(false);
            setCurrentTime(0);
            if (onPlayComplete) {
                onPlayComplete();
            }
        };

        audio.addEventListener('loadedmetadata', handleLoadedMetadata);
        audio.addEventListener('timeupdate', handleTimeUpdate);
        audio.addEventListener('ended', handleEnded);

        return () => {
            audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
            audio.removeEventListener('timeupdate', handleTimeUpdate);
            audio.removeEventListener('ended', handleEnded);
        };
    }, [audioInfo]);

    const togglePlayPause = React.useCallback(() => {
        if (!audioRef.current || !audioInfo) return;

        const audio = audioRef.current;
        const startTime = audioInfo.start || 0;
        const endTime = audioInfo.end || audio.duration;

        if (audio.paused) {
            // Reset to start if at or past the end (use actual audio.currentTime, not state)
            if (audio.currentTime >= endTime - 0.1 || audio.currentTime < startTime) {
                audio.currentTime = startTime;
                setCurrentTime(0);
            }
            audio.play();
            setIsPlaying(true);
        } else {
            audio.pause();
            setIsPlaying(false);
        }
    }, [audioInfo]);

    // Restart from beginning
    const restartAudio = React.useCallback(() => {
        if (!audioRef.current || !audioInfo) return;

        const startTime = audioInfo.start || 0;
        audioRef.current.currentTime = startTime;
        setCurrentTime(0);
        audioRef.current.play();
        setIsPlaying(true);
    }, [audioInfo]);

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    // Keyboard shortcuts
    useEffect(() => {
        if (!autoFocus) return;

        const handleKeyPress = (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            if (e.code === 'Space') {
                e.preventDefault();
                togglePlayPause();
            } else if (e.code === 'KeyR' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                restartAudio();
            }
        };

        window.addEventListener('keydown', handleKeyPress);
        return () => window.removeEventListener('keydown', handleKeyPress);
    }, [togglePlayPause, restartAudio, autoFocus]);

    if (!audioInfo) {
        return (
            <div className="audio-player">
                <div style={{ textAlign: 'center', color: '#6c757d' }}>
                    <Icon name="AlertCircle" size={24} />
                    <p style={{ marginTop: '0.5rem' }}>No audio available</p>
                </div>
            </div>
        );
    }

    const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

    return (
        <div className="audio-player">
            <audio ref={audioRef} preload="auto" />

            <div className="audio-player-controls">
                <Button
                    icon={isPlaying ? 'pi pi-pause' : 'pi pi-play'}
                    rounded
                    size="large"
                    onClick={togglePlayPause}
                    severity={isPlaying ? 'secondary' : 'primary'}
                    style={{ width: '52px', height: '52px', flexShrink: 0 }}
                />

                <div className="audio-progress-bar">
                    <div className="audio-time-display">
                        <span>{formatTime(currentTime)}</span>
                        <span>{formatTime(duration)}</span>
                    </div>
                    <div className="audio-progress-track">
                        <div className="audio-progress-fill" style={{ width: `${progress}%` }} />
                    </div>
                </div>

                <Button
                    icon="pi pi-replay"
                    rounded
                    size="small"
                    onClick={restartAudio}
                    severity="secondary"
                    outlined
                    tooltip="Restart (R)"
                    tooltipOptions={{ position: 'top' }}
                    style={{ width: '36px', height: '36px', flexShrink: 0 }}
                />
            </div>

            <div className="audio-player-hint">
                <span className="keyboard-hint">Space</span> play/pause
                <span style={{ margin: '0 0.5rem', color: 'var(--color-border)' }}>|</span>
                <span className="keyboard-hint">R</span> restart
            </div>
        </div>
    );
};
