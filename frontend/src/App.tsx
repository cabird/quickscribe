// src/App.tsx

import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import HomePage from './pages/HomePage';
import RecordingPage from './pages/RecordingsPage';
import UploadPage from './pages/UploadPage';
import ViewTranscriptionPage from './pages/ViewTranscriptionPage';
function App() {
    return (
        <Router>
            <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/recordings" element={<RecordingPage />} />
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/view_transcription/:transcriptionId" element={<ViewTranscriptionPage />} />
            </Routes> 
	</Router>
    );
}

export default App;

