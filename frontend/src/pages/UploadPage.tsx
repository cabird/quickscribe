// src/pages/UploadPage.tsx

import React, { useState } from 'react';
import axios from 'axios';
import './UploadPage.css';

const UploadPage: React.FC = () => {
    const [file, setFile] = useState<File | null>(null);
    const [progress, setProgress] = useState<number>(0);
    const [status, setStatus] = useState<string>('');

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            setFile(e.target.files[0]);
        }
    };

    const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!file) {
            alert("Please select a file.");
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload', true);

            // Update progress bar
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    setProgress(Math.round(percentComplete));
                }
            });

            // Handle completion
            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    setStatus('File uploaded successfully!');
                    setProgress(100);
                } else {
                    setStatus('File upload failed.');
                }
            });

            // Handle errors
            xhr.addEventListener('error', () => {
                setStatus('An error occurred during the upload.');
            });

            // Send form data
            xhr.send(formData);
        } catch (error) {
            console.error('Upload error:', error);
            setStatus('An error occurred during the upload.');
        }
    };

    return (
        <div className="upload-container">
            <h1>Upload an Audio File</h1>
            <form onSubmit={handleUpload} id="upload-form">
                <input 
                    type="file" 
                    name="file" 
                    accept=".mp3,.m4a" 
                    onChange={handleFileChange} 
                />
                <button type="submit">Upload</button>
            </form>

            {/* Progress Bar */}
            <div className="progress-container">
                <div 
                    className="progress-bar" 
                    style={{ width: `${progress}%` }}
                >
                    {progress}%
                </div>
            </div>

            {/* Status updates */}
            {status && <div className="status">{status}</div>}
        </div>
    );
};

export default UploadPage;

