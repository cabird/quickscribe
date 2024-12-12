import { useState, useRef, useCallback, useEffect } from 'react';
import { MediaRecorder as ExtendableMediaRecorder, register} from 'extendable-media-recorder';
// import the wav encoder
import { connect } from 'extendable-media-recorder-wav-encoder';
import { v4 as uuidv4 } from 'uuid';
import {
  encodeToMp3,
  startAudioStreamSession,
  uploadChunk,
  finishAudioStreamSession,
  getMissingChunks,
  saveRecording
} from '../../api/audiostream';
import { openDB, DBSchema, IDBPDatabase} from 'idb';
import { notifications } from '@mantine/notifications';
import { showNotificationFromError } from '@/Common';


// Define the database schema
interface AudioChunkDB extends DBSchema {
  chunks: {
    key: [string, number]; // sessionId, chunkId
    value: {
      sessionId: string;
      chunkId: number;
      data: Blob;
    };
  };
}

// open the database
const getAudioChunkDB = async (): Promise<IDBPDatabase<AudioChunkDB>> => {
  return await openDB<AudioChunkDB>('audio_chunks', 1, {
    upgrade(db: IDBPDatabase<AudioChunkDB>) {
      if (!db.objectStoreNames.contains('chunks')) {
        db.createObjectStore('chunks', { keyPath: ['sessionId', 'chunkId'] });
      }
    }
  });
};


// check if the wav encoder is already registered
if (!ExtendableMediaRecorder.isTypeSupported('audio/wav')) {
  await register(await connect());
}

interface AudioRecorderState {
  isRecording: boolean;
  volume: number;
  volumeHistory: number[];
  recordingTime: number;
  isLoading: boolean;
  error: string | null;
}

const CHUNK_INTERVAL = 10000; // 10 seconds
const FFT_SIZE = 256;
const BIT_RATE = 192;

const MAX_VOLUME_HISTORY = 50; // Number of bars to show
const VOLUME_SAMPLE_INTERVAL = 50; // 50ms between samples

export const useAudioRecorder = () => {
  const [state, setState] = useState<AudioRecorderState>({
    isRecording: false,
    volume: 0,
    volumeHistory: [],
    recordingTime: 0,
    isLoading: false,
    error: null,
  });

  // Refs
  const isRecordingRef = useRef<boolean>(false);
  const mediaRecorderRef = useRef<any | null>(null);
  const sessionId = useRef<string>();
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const chunkIdRef = useRef<number>(0);
  const timerIntervalRef = useRef<number | null>(null);
  const sampleRate = useRef<number>();
  const channels = useRef<number>();
  const finalChunkProcessedRef = useRef<boolean>(false);
  const processingFinalChunkRef = useRef<boolean>(false);

  const updateVolume = useCallback(() => {
    if (!analyserRef.current || !isRecordingRef.current) return;  
    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);
    const volumeLevel = Math.max(...dataArray);

    setState(prev => ({ ...prev, 
      volume: volumeLevel / 10,
      volumeHistory: [...prev.volumeHistory.slice(-MAX_VOLUME_HISTORY+1),
         volumeLevel / 3],
    }));

    setTimeout(() => {
      requestAnimationFrame(updateVolume);
    }, VOLUME_SAMPLE_INTERVAL);
  }, [isRecordingRef]);

  const handleDataAvailable = async (event: BlobEvent) => {
    if (event.data.size > 0) {
      try {
        const mp3Data = await encodeToMp3(
          channels.current!,
          sampleRate.current!,
          BIT_RATE,
          event.data
        );

        if (!sessionId.current) {
          throw new Error('Session ID is undefined');
        }

        const db = await getAudioChunkDB();
        await db.put('chunks', {
          data: mp3Data,
          sessionId: sessionId.current,
          chunkId: chunkIdRef.current,
        });

        await uploadChunk(sessionId.current, mp3Data, chunkIdRef.current);
        chunkIdRef.current += 1;

        if (processingFinalChunkRef.current) {
          finalChunkProcessedRef.current = true;
        }
      } catch (error) {
        console.error(`Error processing audio chunk: ${error}`);
        setState(prev => ({ ...prev, error: 'Failed to process audio chunk' }));
      }
    }
  };

  const startRecording = async () => {
    try {
      processingFinalChunkRef.current = false;
      finalChunkProcessedRef.current = false;
      chunkIdRef.current = 0;
      setState(prev => ({ ...prev, isLoading: true, error: null }));

      // clear the database of any previous chunks from old sessions
      const db = await getAudioChunkDB();
      await db.clear('chunks');
      
      sessionId.current = uuidv4();
      const successfulStart = await startAudioStreamSession(sessionId.current);
      
      if (!successfulStart) {
        setState(prev => ({ ...prev, isLoading: false, error: 'Failed to start recording session' }));
        throw new Error('Failed to start recording session');
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const track = stream.getAudioTracks()[0];
      sampleRate.current = track.getSettings().sampleRate;
      channels.current = track.getSettings().channelCount;

      // Set up audio context
      audioContextRef.current = new AudioContext();
      analyserRef.current = audioContextRef.current.createAnalyser();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      source.connect(analyserRef.current);
      analyserRef.current.fftSize = FFT_SIZE;

      // Set up media recorder
      mediaRecorderRef.current = new ExtendableMediaRecorder(stream, { mimeType: 'audio/wav' });
      mediaRecorderRef.current.ondataavailable = handleDataAvailable;
      mediaRecorderRef.current.start(CHUNK_INTERVAL);

      // Start timer
      timerIntervalRef.current = window.setInterval(() => {
        setState(prev => ({ ...prev, recordingTime: prev.recordingTime + 1 }));
      }, 1000);

      setState(prev => ({ 
        ...prev, 
        isRecording: true, 
        isLoading: false,
        recordingTime: 0,
        volumeHistory: [],
      }));

      isRecordingRef.current = true;

      // Start volume monitoring
      updateVolume();

    } catch (error) {
      setState(prev => ({ 
        ...prev, 
        isLoading: false, 
        error: error instanceof Error ? error.message : 'Failed to start recording' 
      }));
    }
  };

  const stopRecording = async () => {
    try {
      setState(prev => ({ ...prev, isLoading: true }));
      processingFinalChunkRef.current = true;
      
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
      }

      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }

      // Wait for final chunk
      while (!finalChunkProcessedRef.current) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }

      if (!sessionId.current) {
        setState(prev => ({ ...prev, isLoading: false, error: 'Session ID is undefined' }));
        throw new Error('Session ID is undefined');
      }

      isRecordingRef.current = false;
      setState(prev => ({ 
        ...prev, 
        isRecording: false, 
        isLoading: true 
      }));
            
      await finishAudioStreamSession(sessionId.current, chunkIdRef.current);      
      await sendMissingChunks(sessionId.current);

      setState(prev => ({ 
        ...prev, 
        isRecording: false, 
        isLoading: false 
      }));
    } catch (error) {
      setState(prev => ({ 
        ...prev,
        isRecording: false,
        isLoading: false, 
        error: error instanceof Error ? error.message : 'Failed to stop recording' 
      }));
    }
  };

  const doSaveRecording = async (title: string, description: string) => {
    try {
      if (!sessionId.current) {
        throw new Error('Session ID is undefined');
      }

      setState(prev => ({ ...prev, isLoading: true }));

      const success = await saveRecording(
        sessionId.current,
        title || 'Untitled Recording',
        description || ''
      );

      if (success) {
        notifications.show({
          title: 'Recording Saved',
          message: 'Your recording has been saved successfully',
        });
      } else {
        throw new Error('Failed to save recording');
      }

      setState(prev => ({ 
        ...prev,
        isLoading: false,
      }));

    } catch (error) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to save recording'
      }));
    }
  }
  
  // send missing chunks
  const sendMissingChunks = async (sessionId: string) => {

    const db = await getAudioChunkDB();
    await db.clear('chunks');

    while (true) {
      const missingChunks = await getMissingChunks(sessionId);
      if (missingChunks.length === 0) {
        break;
      }
      console.error(`Missing chunks: ${missingChunks.join(', ')}`);

      // try to send the missing chunks
      for (const chunkId of missingChunks) {
        try {
          const chunk = await db.get('chunks', [sessionId, chunkId]);
          if (chunk) {
            await uploadChunk(sessionId, chunk.data, chunkId);
          } else {
            setState(prev => ({ ...prev, error: `Chunk ${chunkId} not found in IndexedDB` }));
            console.error(`Chunk ${chunkId} not found in IndexedDB`);
          }
        } catch (error) {
          setState(prev => ({ ...prev, error: `Error getting chunk ${chunkId} from IndexedDB: ${error}` }));
          console.error(`Error getting chunk ${chunkId} from IndexedDB: ${error}`);
        }
      }
    }
  }

  // Cleanup
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
      }
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, []);

  return {
    ...state,
    startRecording,
    stopRecording,
  };
};