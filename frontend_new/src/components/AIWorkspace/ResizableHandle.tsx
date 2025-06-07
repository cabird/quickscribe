import { useState, useCallback } from 'react';
import { Box } from '@mantine/core';

interface ResizableHandleProps {
  onResize: (newHeight: number) => void;
  minHeight?: number;
  maxHeight?: number;
}

export function ResizableHandle({ onResize, minHeight = 150, maxHeight = window.innerHeight * 0.7 }: ResizableHandleProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    
    const startY = e.clientY;
    const startHeight = document.querySelector('[data-resizable-panel]')?.clientHeight || 350;
    
    const handleMouseMove = (e: MouseEvent) => {
      const diffY = startY - e.clientY; // Inverted - dragging up increases height
      const newHeight = startHeight + diffY;
      
      if (newHeight >= minHeight && newHeight <= maxHeight) {
        onResize(newHeight);
      }
    };
    
    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [onResize, minHeight, maxHeight]);

  return (
    <Box
      onMouseDown={handleMouseDown}
      style={{
        position: 'absolute',
        top: -4,
        left: 0,
        right: 0,
        height: 8,
        backgroundColor: isDragging ? 'var(--mantine-color-blue-6)' : 'var(--mantine-color-gray-4)',
        cursor: 'row-resize',
        zIndex: 10,
        transition: isDragging ? 'none' : 'background-color 0.2s ease',
      }}
      __vars={{
        '--hover-color': 'var(--mantine-color-blue-6)',
      }}
      sx={{
        '&:hover': {
          backgroundColor: 'var(--hover-color)',
        },
      }}
    />
  );
}