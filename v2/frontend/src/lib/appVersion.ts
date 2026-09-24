/**
 * Version of the frontend bundle that is actually running, stamped at build
 * time from backend/VERSION (02-build-push.sh passes it as VITE_APP_VERSION).
 * "dev" under the Vite dev server. Compare with the server's /api/version to
 * detect a window still running an older build after a deploy.
 */
export const APP_VERSION: string = import.meta.env.VITE_APP_VERSION || "dev";
