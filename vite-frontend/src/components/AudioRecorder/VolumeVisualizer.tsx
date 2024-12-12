import React from 'react';

interface VolumeVisualizerProps {
  volumeHistory: number[];
  isRecording: boolean;
}

const VolumeVisualizer: React.FC<VolumeVisualizerProps> = ({ volumeHistory, isRecording }) => {
  return (
    <div 
      style={{ 
        display: 'flex',
        alignItems: 'center',
        gap: '2px',
        height: '60px',
        padding: '10px',
        backgroundColor: '#F5f5f5',
        borderRadius: '8px',
        overflow: 'hidden'
      }}
    >
      {volumeHistory.map((volume, index) => (
        <div
          key={index}
          style={{
            width: '2px',
            height: `${Math.max(2, volume)}%`,
            backgroundColor: '#FF0000',
            borderRadius: '2px',
            transition: 'height 0.1s ease-in-out'
          }}
        />
      ))}
      {/* Fill empty space with placeholder bars when not enough history */}
      {[...Array(Math.max(0, 50 - volumeHistory.length))].map((_, index) => (
        <div
          key={`empty-${index}`}
          style={{
            width: '2px',
            height: '2%',
            backgroundColor: '#FF0000',
            borderRadius: '2px',
          }}
        />
      ))}
    </div>
  );
};

export default VolumeVisualizer;