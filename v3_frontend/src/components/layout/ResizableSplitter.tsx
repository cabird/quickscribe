import { useState, useCallback, useRef, useEffect } from 'react';
import { makeStyles } from '@fluentui/react-components';

const useStyles = makeStyles({
  splitter: {
    width: '4px',
    cursor: 'col-resize',
    backgroundColor: '#e0e0e0',
    flexShrink: 0,
    position: 'relative',
    ':hover': {
      backgroundColor: '#2563EB',
    },
  },
  splitterActive: {
    backgroundColor: '#2563EB',
  },
});

interface ResizableSplitterProps {
  onResize: (delta: number) => void;
}

export function ResizableSplitter({ onResize }: ResizableSplitterProps) {
  const styles = useStyles();
  const [isDragging, setIsDragging] = useState(false);
  const startXRef = useRef(0);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    startXRef.current = e.clientX;
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const delta = e.clientX - startXRef.current;
      startXRef.current = e.clientX;
      onResize(delta);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, onResize]);

  return (
    <div
      className={`${styles.splitter} ${isDragging ? styles.splitterActive : ''}`}
      onMouseDown={handleMouseDown}
    />
  );
}
