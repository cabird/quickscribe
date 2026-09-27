// Store only the opaque transaction ID, never an arbitrary return URL.
const KEY = "qs_oauth_request";
const ID = /^[A-Za-z0-9_-]{43}$/;

export function captureOAuthRequest(url: URL, storage: Storage): void {
  if (url.pathname.replace(/\/+$/, "").toLowerCase() !== "/oauth/consent") return;
  const ids = url.searchParams.getAll("request");
  if (ids.length === 1 && ID.test(ids[0])) storage.setItem(KEY, ids[0]);
  else storage.removeItem(KEY);
}

export function takeOAuthReturnPath(storage: Storage): string | null {
  const id = storage.getItem(KEY);
  storage.removeItem(KEY);
  return id && ID.test(id) ? `/oauth/consent?request=${encodeURIComponent(id)}` : null;
}
