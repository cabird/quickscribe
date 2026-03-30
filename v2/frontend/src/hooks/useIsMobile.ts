import { useState, useEffect } from "react";

const MOBILE_BREAKPOINT = 768;

/**
 * Returns `true` when the viewport width is at or below the mobile breakpoint
 * (768 px).  Updates reactively on window resize.
 */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== "undefined"
      ? window.innerWidth <= MOBILE_BREAKPOINT
      : false,
  );

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`);

    const handler = (e: MediaQueryListEvent) => {
      setIsMobile(e.matches);
    };

    // Set initial value
    setIsMobile(mql.matches);

    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  return isMobile;
}
