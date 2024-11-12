import React, { useState } from 'react';

interface SpeakerLabelDialogProps {
    speakerSummaries: { [key: string]: string };
    isLoading: boolean;
    onClose: () => void;
    onAccept: (speakerLabels: { [key: string]: string }) => void;
}

const SpeakerLabelDialog: React.FC<SpeakerLabelDialogProps> = ({ speakerSummaries, isLoading, onClose, onAccept }) => {
    const [labels, setLabels] = useState<{ [key: string]: string }>({});

    const handleChange = (speaker: string, label: string) => {
        setLabels({ ...labels, [speaker]: label });
    };

    const handleAccept = () => {
        onAccept(labels);
        onClose();
    };

    // Render a loading indicator if data is still being fetched
    if (isLoading) {
        return <div className="dialog"><p>Loading speaker summaries...</p></div>;
    }

    return (
        <div className="dialog">
            <h2>Label Speakers</h2>
            {Object.entries(speakerSummaries).map(([speaker, summary]) => (
                <div key={speaker}>
                    <p>{summary}</p>
                    <input
                        type="text"
                        placeholder={`Label for ${speaker}`}
                        value={labels[speaker] || ''}
                        onChange={(e) => handleChange(speaker, e.target.value)}
                    />
                </div>
            ))}
            <button onClick={handleAccept}>Accept</button>
            <button onClick={onClose}>Cancel</button>
        </div>
    );
};

export default SpeakerLabelDialog;