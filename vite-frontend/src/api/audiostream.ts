import fs from 'fs';
import axios from 'axios';
import { Mp3Encoder } from '@breezystack/lamejs';

const API_BASE_URL = "/audiostream";

async function startAudioStreamSession(sessionId: string): Promise<boolean> {
    try {
        const response = await axios.post(`${API_BASE_URL}/start`, { session_id: sessionId });
        console.info("Recording started successfully.");
        return true;
    } catch (error) {
        console.error(`Failed to start recording: ${error}`);
        alert(`Failed to start recording: ${error}`);
        return false;
    }
}

async function uploadChunk(sessionId: string, chunkData: Blob, chunkId: number): Promise<boolean> {
    const formData = new FormData();
    formData.append("chunk_data", chunkData);
    formData.append("session_id", sessionId);
    formData.append("chunk_id", chunkId.toString());

    try {
        const response = await axios.post(`${API_BASE_URL}/upload_chunk`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
        console.info(`Uploaded chunk ${chunkId}. Response:`, response.data);
        return true;
    } catch (error) {
        console.error(`Failed to upload chunk ${chunkId}: ${error}`);
        alert(`Failed to upload chunk ${chunkId}: ${error}`);
        return false;
    }
}

async function finishAudioStreamSession(sessionId: string, numberOfChunks: number): Promise<boolean> {
    try {
        const response = await axios.post(`${API_BASE_URL}/finish`, {
            session_id: sessionId,
            number_of_chunks: numberOfChunks
        });
        console.info("Recording finished successfully.");
        return true;
    } catch (error) {
        console.error(`Failed to finish recording: ${error}`);
        alert(`Failed to finish recording: ${error}`);
        return false;
    }
}

async function saveRecording(sessionId: string, title: string, description: string): Promise<boolean> {
    try {
        const response = await axios.post(`${API_BASE_URL}/save_recording`, 
            { session_id: sessionId, title: title, description: description});
        console.info("recording saved successfully");
        console.log(response.data);
        return true;
    } catch (error) {
        console.error(`Failed to save recording: ${error}`);
        alert(`Failed to save recording: ${error}`);
        return false;
    }
}

async function getMissingChunks(sessionId: string): Promise<number[]> {
    try {   
        const response = await axios.get(`${API_BASE_URL}/check_missing`, { params: { session_id: sessionId } });
        return response.data.missing_chunks || [];
    } catch (error) {
        console.error(`Failed to get missing chunks: ${error}`);
        alert(`Failed to get missing chunks: ${error}`);
        return [];
    }
}

async function encodeToMp3(channels: number, sampleRate: number, bitRate: number, blob: Blob): Promise<Blob> {
    const arrayBuffer = await blob.arrayBuffer();
    const mp3encoder = new Mp3Encoder(channels, sampleRate, bitRate);
    const samples = new Int16Array(arrayBuffer);

    let outputBuffer: Uint8Array[] = []
    let remainingSamples = samples.length;

    while (remainingSamples > 0) {
        const samplesToProcess = Math.min(remainingSamples, 1152);
        const mp3Buffer = mp3encoder.encodeBuffer(
            samples.subarray(samples.length - remainingSamples, samples.length - remainingSamples + samplesToProcess)
        );
        if (mp3Buffer.length > 0) outputBuffer.push(new Uint8Array(mp3Buffer));
        remainingSamples -= samplesToProcess;
    }

    const endBuffer = mp3encoder.flush();
    if (endBuffer.length > 0) outputBuffer.push(new Uint8Array(endBuffer));

    return new Blob(outputBuffer, { type: 'audio/mp3' });
};

export { startAudioStreamSession, uploadChunk, saveRecording, finishAudioStreamSession, getMissingChunks, encodeToMp3 };


