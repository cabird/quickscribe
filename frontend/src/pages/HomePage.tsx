// src/pages/HomePage.tsx

import React from 'react';
import { Link } from 'react-router-dom';
import './HomePage.css';

const HomePage: React.FC = () => {
    return (
        <div className="home-container">
            <h1>Welcome to QuickScribe</h1>
            <p>Your go-to platform for audio transcription and file management.</p>
            <div className="link-container">
                <Link to="/recordings" className="home-link">View Recordings</Link>
                <Link to="/upload" className="home-link">Upload a New Recording</Link>
            </div>
        </div>
    );
};

export default HomePage;

