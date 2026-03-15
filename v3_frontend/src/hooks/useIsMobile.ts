import { useState, useEffect } from 'react';
import { LAYOUT } from '../config/styles';

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(
    () => window.innerWidth < LAYOUT.mobileBreakpoint
  );

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${LAYOUT.mobileBreakpoint - 1}px)`);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return isMobile;
}
