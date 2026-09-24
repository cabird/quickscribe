import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { APP_VERSION } from "@/lib/appVersion";
import { useVersion } from "@/lib/queries";

/**
 * Shown when the server has been redeployed since this window loaded, e.g.
 * an installed desktop app left open across a deploy. Never reloads by
 * itself, so nothing in progress is interrupted.
 */
export function UpdateBanner() {
  const { data: serverVersion } = useVersion();

  if (APP_VERSION === "dev" || !serverVersion || serverVersion === APP_VERSION) {
    return null;
  }

  return (
    <div
      role="status"
      className="flex items-center justify-center gap-3 border-b bg-amber-50 px-4 py-1.5 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-100"
    >
      <span>
        A different version of QuickScribe is deployed ({serverVersion}; this window is
        running {APP_VERSION}).
      </span>
      <Button
        size="sm"
        variant="outline"
        className="h-6 gap-1 px-2 text-xs"
        onClick={() => window.location.reload()}
      >
        <RefreshCw className="h-3 w-3" />
        Reload
      </Button>
    </div>
  );
}
