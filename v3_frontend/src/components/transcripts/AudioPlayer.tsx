import { useState, useRef, useEffect, useImperativeHandle, forwardRef } from 'react';
import { makeStyles, Button, tokens } from '@fluentui/react-components';
import { Play24Regular, Pause24Regular } from '@fluentui/react-icons';

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
});

export interface AudioPlayerHandle {
  seekTo: (timeMs: number) => void;
}

interface AudioPlayerProps {
  audioUrl: string;
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '00:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

export const AudioPlayer = forwardRef<AudioPlayerHandle, AudioPlayerProps>(
  function AudioPlayer({ audioUrl }, ref) {
    const styles = useStyles();
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);

    // Expose seekTo method to parent
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
    }));

    // Audio event handlers
    useEffect(() => {
      const audio = audioRef.current;
      if (!audio) return;

      const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
      const handleDurationChange = () => setDuration(audio.duration);
      const handleEnded = () => setIsPlaying(false);
      const handlePlay = () => setIsPlaying(true);
      const handlePause = () => setIsPlaying(false);

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
    }, [audioUrl]);

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
      </div>
    );
  }
);
