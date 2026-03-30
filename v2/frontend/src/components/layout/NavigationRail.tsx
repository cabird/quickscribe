import { NavLink } from "react-router-dom";
import { useIsMobile } from "@/hooks/useIsMobile";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useCurrentUser, useVersion } from "@/lib/queries";
import { authEnabled, getMsalInstance } from "@/lib/auth";
import { LogOut } from "lucide-react";

// ---------------------------------------------------------------------------
// Icons (inline SVG to avoid extra dependency)
// ---------------------------------------------------------------------------

function MicIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
  );
}

function UsersIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function ShieldCheckIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function ActivityIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2" />
    </svg>
  );
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function LibraryIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function ChevronLeftIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Navigation items
// ---------------------------------------------------------------------------

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { to: "/recordings", label: "Recordings", icon: MicIcon },
  { to: "/people", label: "People", icon: UsersIcon },
  { to: "/reviews", label: "Reviews", icon: ShieldCheckIcon },
  { to: "/jobs", label: "Jobs", icon: ActivityIcon },
  { to: "/search", label: "Search", icon: SearchIcon },
  { to: "/collections", label: "Collections", icon: LibraryIcon },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

// ---------------------------------------------------------------------------
// Helper: get initials from a name
// ---------------------------------------------------------------------------

function getInitials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

// ---------------------------------------------------------------------------
// Desktop sidebar
// ---------------------------------------------------------------------------

function DesktopSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const { data: user } = useCurrentUser();
  const { data: version } = useVersion();

  const displayName = user?.name || "User";
  const email = user?.email || "";
  const initials = getInitials(user?.name);
  const [showUserMenu, setShowUserMenu] = useState(false);

  const handleSignOut = () => {
    if (authEnabled) {
      const msal = getMsalInstance();
      msal.logoutRedirect({
        postLogoutRedirectUri: window.location.origin,
      });
    }
  };

  return (
    <aside
      className={cn(
        "hidden md:flex flex-col border-r border-brand-800 transition-all duration-200",
        collapsed ? "w-16" : "w-56",
      )}
      style={{ backgroundColor: "#0078D4", color: "#ffffff" }}
    >
      {/* Header */}
      <div className="flex items-center h-14 px-3">
        {!collapsed && (
          <span className="text-lg font-semibold tracking-tight truncate text-white">
            QuickScribe
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          className={cn("ml-auto h-8 w-8 text-white hover:bg-white/20 hover:text-white", collapsed && "mx-auto")}
          onClick={() => setCollapsed((v) => !v)}
        >
          {collapsed ? (
            <ChevronRightIcon className="h-4 w-4" />
          ) : (
            <ChevronLeftIcon className="h-4 w-4" />
          )}
        </Button>
      </div>

      <div className="mx-3 border-t border-white/20" />

      {/* Nav links */}
      <nav className="flex-1 flex flex-col gap-1 p-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const link = (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors text-white/85",
                  "hover:bg-white/15 hover:text-white",
                  isActive &&
                    "bg-white/20 text-white",
                  collapsed && "justify-center px-0",
                )
              }
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </NavLink>
          );

          if (collapsed) {
            return (
              <Tooltip key={item.to}>
                <TooltipTrigger className="contents">
                  {link}
                </TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          }

          return link;
        })}
      </nav>

      {/* Footer: User section + Version */}
      <div className="mt-auto px-2 pb-2 space-y-2">
        <div className="mx-1 border-t border-white/20 mb-2" />

        {/* User section */}
        <div className="relative">
          <button
            className={cn(
              "flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-white/15",
              collapsed && "justify-center px-0"
            )}
            onClick={() => setShowUserMenu(!showUserMenu)}
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/20 text-xs font-semibold text-white">
              {initials}
            </span>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-white">
                  {displayName}
                </p>
                {email && (
                  <p className="truncate text-[11px] text-white/60">{email}</p>
                )}
              </div>
            )}
          </button>

          {/* User menu popover */}
          {showUserMenu && (
            <>
              {/* Backdrop to close */}
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowUserMenu(false)}
              />
              <div className="absolute bottom-full left-0 z-50 mb-1 w-52 rounded-md border bg-popover p-1 text-popover-foreground shadow-lg">
                <div className="px-3 py-2 border-b">
                  <p className="text-sm font-semibold">{displayName}</p>
                  {email && (
                    <p className="text-xs text-muted-foreground">{email}</p>
                  )}
                </div>
                {authEnabled ? (
                  <button
                    className="flex w-full items-center gap-2 rounded-sm px-3 py-1.5 text-sm hover:bg-accent transition-colors"
                    onClick={handleSignOut}
                  >
                    <LogOut className="h-4 w-4" />
                    Sign Out
                  </button>
                ) : (
                  <div className="px-3 py-1.5 text-xs text-muted-foreground">
                    Dev Mode
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Version */}
        <p
          className={cn(
            "text-[11px] text-white/40 select-text",
            collapsed ? "text-center" : "px-2"
          )}
          title={`API Version: ${version ?? "..."}`}
        >
          {version ? `v${version}` : ""}
        </p>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Mobile bottom bar
// ---------------------------------------------------------------------------

/** Mobile: show 5 primary tabs (drop Search to keep it compact). */
const mobileItems = navItems.filter((i) => i.to !== "/search");

function MobileBottomBar() {
  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 z-50 flex items-center justify-around border-t border-border bg-background h-14"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      {mobileItems.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-0.5 text-[11px] font-medium py-1 px-3 transition-colors",
                isActive
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground",
              )
            }
          >
            <Icon className="h-5 w-5" />
            <span>{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Exported composite component
// ---------------------------------------------------------------------------

export function NavigationRail() {
  const isMobile = useIsMobile();

  if (isMobile) return <MobileBottomBar />;
  return <DesktopSidebar />;
}
