import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Pause, Play, Volume2, VolumeX } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AudioPlayerHandle {
  seekTo(timeMs: number): void;
  pause(): void;
  getIsPlaying(): boolean;
  getCurrentTimeMs(): number;
}

interface AudioPlayerProps {
  src: string | null;
  className?: string;
  onPlayStateChange?: (isPlaying: boolean, currentTimeMs: number) => void;
}

export const AudioPlayer = forwardRef<AudioPlayerHandle, AudioPlayerProps>(
  function AudioPlayer({ src, className, onPlayStateChange }, ref) {
    const audioRef = useRef<HTMLAudioElement>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [volume, _setVolume] = useState(1);
    const [isMuted, setIsMuted] = useState(false);

    useImperativeHandle(ref, () => ({
      seekTo(timeMs: number) {
        const audio = audioRef.current;
        if (!audio) return;
        audio.currentTime = timeMs / 1000;
        audio.play().catch(() => {});
      },
      pause() {
        audioRef.current?.pause();
      },
      getIsPlaying() {
        return isPlaying;
      },
      getCurrentTimeMs() {
        return (audioRef.current?.currentTime ?? 0) * 1000;
      },
    }));

    const handleTimeUpdate = useCallback(() => {
      const audio = audioRef.current;
      if (!audio) return;
      setCurrentTime(audio.currentTime);
      onPlayStateChange?.(!audio.paused, audio.currentTime * 1000);
    }, [onPlayStateChange]);

    useEffect(() => {
      const audio = audioRef.current;
      if (!audio) return;

      const onPlay = () => setIsPlaying(true);
      const onPause = () => setIsPlaying(false);
      const onLoaded = () => setDuration(audio.duration || 0);

      audio.addEventListener("play", onPlay);
      audio.addEventListener("pause", onPause);
      audio.addEventListener("loadedmetadata", onLoaded);
      audio.addEventListener("timeupdate", handleTimeUpdate);

      return () => {
        audio.removeEventListener("play", onPlay);
        audio.removeEventListener("pause", onPause);
        audio.removeEventListener("loadedmetadata", onLoaded);
        audio.removeEventListener("timeupdate", handleTimeUpdate);
      };
    }, [handleTimeUpdate]);

    const togglePlay = useCallback(() => {
      const audio = audioRef.current;
      if (!audio) return;
      if (audio.paused) {
        audio.play().catch(() => {});
      } else {
        audio.pause();
      }
    }, []);

    const handleSeek = useCallback((value: number | readonly number[]) => {
      const audio = audioRef.current;
      if (!audio) return;
      const v = Array.isArray(value) ? value[0] : value;
      audio.currentTime = v;
    }, []);

    const toggleMute = useCallback(() => {
      const audio = audioRef.current;
      if (!audio) return;
      if (isMuted) {
        audio.volume = volume || 0.5;
        setIsMuted(false);
      } else {
        audio.volume = 0;
        setIsMuted(true);
      }
    }, [isMuted, volume]);

    if (!src) return null;

    return (
      <div className={cn("flex items-center gap-2 overflow-hidden rounded-lg border bg-card p-2", className)}>
        <audio ref={audioRef} src={src} preload="metadata" />

        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={togglePlay}>
          {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </Button>

        <span className="shrink-0 text-center text-xs tabular-nums text-muted-foreground">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>

        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={toggleMute}>
          {isMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
        </Button>

        <div className="min-w-0 flex-1">
          <Slider
            value={[currentTime]}
            max={duration || 1}
            step={0.1}
            onValueChange={handleSeek}
          />
        </div>
      </div>
    );
  }
);

function formatTime(seconds: number): string {
  if (!seconds || !isFinite(seconds)) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
