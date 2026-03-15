import { useState, useRef, useEffect, useImperativeHandle, forwardRef } from 'react';
import { makeStyles, Button, tokens, Tooltip } from '@fluentui/react-components';
import { Play24Regular, Pause24Regular, Speaker224Regular, SpeakerMute24Regular } from '@fluentui/react-icons';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '8px 16px',
    backgroundColor: tokens.colorNeutralBackground3,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  playButton: {
    minWidth: '32px',
    width: '32px',
    height: '32px',
  },
  time: {
    fontSize: '13px',
    color: tokens.colorNeutralForeground2,
    fontFamily: 'monospace',
    minWidth: '100px',
  },
  progressBar: {
    flex: 1,
    height: '4px',
    backgroundColor: tokens.colorNeutralBackground5,
    borderRadius: '2px',
    cursor: 'pointer',
    position: 'relative',
  },
  progressFill: {
    height: '100%',
    backgroundColor: tokens.colorBrandBackground,
    borderRadius: '2px',
    transition: 'width 0.1s',
  },
  volumeContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    marginLeft: '8px',
  },
  volumeButton: {
    minWidth: '32px',
    width: '32px',
    height: '32px',
  },
  volumeSlider: {
    width: '80px',
    height: '4px',
    appearance: 'none',
    backgroundColor: tokens.colorNeutralBackground5,
    borderRadius: '2px',
    cursor: 'pointer',
    '::-webkit-slider-thumb': {
      appearance: 'none',
      width: '12px',
      height: '12px',
      borderRadius: '50%',
      backgroundColor: tokens.colorBrandBackground,
      cursor: 'pointer',
    },
    '::-moz-range-thumb': {
      width: '12px',
      height: '12px',
      borderRadius: '50%',
      backgroundColor: tokens.colorBrandBackground,
      cursor: 'pointer',
      border: 'none',
    },
  },
});

export interface AudioPlayerHandle {
  seekTo: (timeMs: number) => void;
  pause: () => void;
  getIsPlaying: () => boolean;
  getCurrentTimeMs: () => number;
}

interface AudioPlayerProps {
  audioUrl: string;
  onPlayStateChange?: (isPlaying: boolean, currentTimeMs: number) => void;
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '00:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

export const AudioPlayer = forwardRef<AudioPlayerHandle, AudioPlayerProps>(
  function AudioPlayer({ audioUrl, onPlayStateChange }, ref) {
    const styles = useStyles();
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [volume, setVolume] = useState(1);
    const [isMuted, setIsMuted] = useState(false);

    // Expose methods to parent
    useImperativeHandle(ref, () => ({
      seekTo: (timeMs: number) => {
        const audio = audioRef.current;
        if (!audio) {
          console.log('[AudioPlayer] No audio element available');
          return;
        }
        const timeSeconds = timeMs / 1000;
        console.log(`[AudioPlayer] Seeking to ${timeSeconds.toFixed(2)}s (${timeMs}ms)`);
        audio.currentTime = timeSeconds;
        audio.play().catch(err => {
          console.error('[AudioPlayer] Playback failed:', err);
        });
      },
      pause: () => {
        const audio = audioRef.current;
        if (audio) {
          audio.pause();
        }
      },
      getIsPlaying: () => isPlaying,
      getCurrentTimeMs: () => currentTime * 1000,
    }));

    // Audio event handlers
    useEffect(() => {
      const audio = audioRef.current;
      if (!audio) return;

      const handleTimeUpdate = () => {
        setCurrentTime(audio.currentTime);
        if (onPlayStateChange && !audio.paused) {
          onPlayStateChange(true, audio.currentTime * 1000);
        }
      };
      const handleDurationChange = () => setDuration(audio.duration);
      const handleEnded = () => {
        setIsPlaying(false);
        onPlayStateChange?.(false, audio.currentTime * 1000);
      };
      const handlePlay = () => {
        setIsPlaying(true);
        onPlayStateChange?.(true, audio.currentTime * 1000);
      };
      const handlePause = () => {
        setIsPlaying(false);
        onPlayStateChange?.(false, audio.currentTime * 1000);
      };

      audio.addEventListener('timeupdate', handleTimeUpdate);
      audio.addEventListener('durationchange', handleDurationChange);
      audio.addEventListener('ended', handleEnded);
      audio.addEventListener('play', handlePlay);
      audio.addEventListener('pause', handlePause);

      return () => {
        audio.removeEventListener('timeupdate', handleTimeUpdate);
        audio.removeEventListener('durationchange', handleDurationChange);
        audio.removeEventListener('ended', handleEnded);
        audio.removeEventListener('play', handlePlay);
        audio.removeEventListener('pause', handlePause);
      };
    }, [audioUrl, onPlayStateChange]);

    const handleTogglePlayPause = () => {
      const audio = audioRef.current;
      if (!audio) return;

      if (isPlaying) {
        audio.pause();
      } else {
        audio.play().catch(err => console.error('[AudioPlayer] Playback failed:', err));
      }
    };

    const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
      const audio = audioRef.current;
      if (!audio || !duration) return;

      const rect = e.currentTarget.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const percentage = clickX / rect.width;
      audio.currentTime = percentage * duration;
    };

    const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newVolume = parseFloat(e.target.value);
      setVolume(newVolume);
      if (audioRef.current) {
        audioRef.current.volume = newVolume;
        if (newVolume > 0 && isMuted) {
          setIsMuted(false);
        }
      }
    };

    const handleToggleMute = () => {
      const audio = audioRef.current;
      if (!audio) return;

      if (isMuted) {
        audio.volume = volume;
        setIsMuted(false);
      } else {
        audio.volume = 0;
        setIsMuted(true);
      }
    };

    return (
      <div className={styles.container}>
        <audio ref={audioRef} src={audioUrl} preload="metadata" />
        <Button
          appearance="subtle"
          className={styles.playButton}
          icon={isPlaying ? <Pause24Regular /> : <Play24Regular />}
          onClick={handleTogglePlayPause}
        />
        <span className={styles.time}>
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
        <div className={styles.progressBar} onClick={handleProgressClick}>
          <div
            className={styles.progressFill}
            style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}
          />
        </div>
        <div className={styles.volumeContainer}>
          <Tooltip content={isMuted ? 'Unmute' : 'Mute'} relationship="label">
            <Button
              appearance="subtle"
              className={styles.volumeButton}
              icon={isMuted || volume === 0 ? <SpeakerMute24Regular /> : <Speaker224Regular />}
              onClick={handleToggleMute}
            />
          </Tooltip>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={isMuted ? 0 : volume}
            onChange={handleVolumeChange}
            className={styles.volumeSlider}
            aria-label="Volume"
          />
        </div>
      </div>
    );
  }
);
