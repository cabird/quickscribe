import { Outlet } from "react-router-dom";
import { NavigationRail } from "./NavigationRail";
import { UpdateBanner } from "./UpdateBanner";
import { useIsMobile } from "@/hooks/useIsMobile";

/**
 * Root layout wrapping all routed pages.
 *
 * - Desktop: left sidebar  +  scrollable content area
 * - Mobile:  bottom tab bar  +  full-width content with bottom padding
 */
export function Layout() {
  const isMobile = useIsMobile();

  return (
    <div className="flex h-dvh overflow-hidden bg-background text-foreground">
      {/* Sidebar (desktop only — hidden via Tailwind on mobile) */}
      <NavigationRail />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <UpdateBanner />

        {/* Main content */}
        <main
          className={
            "min-h-0 flex-1 overflow-y-auto" +
            // On mobile add bottom padding so content isn't hidden behind the
            // fixed bottom navigation bar.
            (isMobile ? " pb-16" : "")
          }
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
