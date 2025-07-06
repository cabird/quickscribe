import { useState, useRef, useEffect, useCallback } from 'react';
import { Button, Slider, Text, Group, Paper, ActionIcon } from '@mantine/core';
import { LuPlay, LuPause, LuSkipBack, LuSkipForward, LuX } from 'react-icons/lu';
import axios from 'axios';

interface AudioPlayerProps {
  recordingId: string;
  onTimeUpdate?: (currentTime: number) => void;
  onClose?: () => void;
}

export function AudioPlayer({ recordingId, onTimeUpdate, onClose }: AudioPlayerProps) {
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const audioRef = useRef<HTMLAudioElement>(null);

  // Fetch audio URL when component mounts
  useEffect(() => {
    const fetchAudioUrl = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const response = await axios.get(`/api/recording/${recordingId}/audio-url`);
        setAudioUrl(response.data.audio_url);
      } catch (err: any) {
        console.error('Failed to fetch audio URL:', err);
        const errorMessage = err.response?.data?.error || 'Failed to load audio';
        setError(errorMessage);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAudioUrl();
  }, [recordingId]);

  // Update time state when audio plays
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !audioUrl) return;

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
      onTimeUpdate?.(audio.currentTime);
      
      // Also check duration in case it wasn't available before
      if (audio.duration && !isNaN(audio.duration) && audio.duration !== duration) {
        setDuration(audio.duration);
      }
    };

    const handleLoadedMetadata = () => {
      setDuration(audio.duration);
    };

    const handleEnded = () => {
      setIsPlaying(false);
    };

    const handleCanPlay = () => {
      // Audio is ready to play
    };

    const handleError = (e: Event) => {
      console.error('Audio error:', e);
    };

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('canplay', handleCanPlay);
    audio.addEventListener('error', handleError);

    // Force load metadata
    audio.load();

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('canplay', handleCanPlay);
      audio.removeEventListener('error', handleError);
    };
  }, [audioUrl, onTimeUpdate]);

  const togglePlayPause = async () => {
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
    } else {
      try {
        await audioRef.current.play();
        // Check duration after play starts
        if (audioRef.current.duration && !isNaN(audioRef.current.duration)) {
          setDuration(audioRef.current.duration);
        }
      } catch (error) {
        console.error('Error playing audio:', error);
      }
    }
    setIsPlaying(!isPlaying);
  };

  const seek = (time: number) => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = time;
    setCurrentTime(time);
  };

  const seekToTimestamp = useCallback((milliseconds: number) => {
    const seconds = milliseconds / 1000;
    seek(seconds);
    if (!isPlaying && audioRef.current) {
      audioRef.current.play();
      setIsPlaying(true);
    }
  }, [seek, isPlaying]);

  const skip = (seconds: number) => {
    if (!audioRef.current) return;
    const newTime = Math.max(0, Math.min(duration, currentTime + seconds));
    seek(newTime);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Expose seekToTimestamp method
  useEffect(() => {
    // Store the seekToTimestamp function on the window for easy access
    // This allows transcript phrases to trigger playback
    (window as any).audioPlayerSeekTo = (ms: number) => {
      const seconds = ms / 1000;
      if (audioRef.current) {
        audioRef.current.currentTime = seconds;
        setCurrentTime(seconds);
        if (!isPlaying) {
          audioRef.current.play();
          setIsPlaying(true);
        }
      }
    };
    
    return () => {
      delete (window as any).audioPlayerSeekTo;
    };
  }, [isPlaying]);

  if (error) {
    return (
      <Paper p="md" withBorder bg="red.1">
        <Group justify="space-between">
          <Text c="red">{error}</Text>
          {onClose && (
            <ActionIcon onClick={onClose} variant="subtle">
              <LuX size={16} />
            </ActionIcon>
          )}
        </Group>
      </Paper>
    );
  }

  if (isLoading) {
    return (
      <Paper p="md" withBorder>
        <Text>Loading audio...</Text>
      </Paper>
    );
  }

  return (
    <Paper p="md" withBorder style={{ position: 'sticky', bottom: 0, zIndex: 100 }}>
      {audioUrl && (
        <audio 
          ref={audioRef} 
          src={audioUrl} 
          preload="metadata"
        />
      )}
      
      <Group gap="xs">
        <ActionIcon onClick={() => skip(-10)} variant="subtle" disabled={!audioUrl}>
          <LuSkipBack size={20} />
        </ActionIcon>
        
        <ActionIcon 
          onClick={togglePlayPause} 
          variant="filled" 
          size="lg"
          disabled={!audioUrl}
        >
          {isPlaying ? <LuPause size={20} /> : <LuPlay size={20} />}
        </ActionIcon>
        
        <ActionIcon onClick={() => skip(10)} variant="subtle" disabled={!audioUrl}>
          <LuSkipForward size={20} />
        </ActionIcon>
        
        <Text size="sm" style={{ minWidth: '40px' }}>
          {formatTime(currentTime)}
        </Text>
        
        <Slider
          value={currentTime}
          onChange={seek}
          max={duration}
          style={{ flex: 1 }}
          disabled={!audioUrl}
          label={(value) => formatTime(value)}
        />
        
        <Text size="sm" style={{ minWidth: '40px' }}>
          {formatTime(duration)}
        </Text>
        
        {onClose && (
          <ActionIcon onClick={onClose} variant="subtle" ml="md">
            <LuX size={16} />
          </ActionIcon>
        )}
      </Group>
    </Paper>
  );
}