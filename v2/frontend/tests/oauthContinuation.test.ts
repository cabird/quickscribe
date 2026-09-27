import assert from "node:assert/strict";
import { test } from "node:test";
import { captureOAuthRequest, takeOAuthReturnPath } from "../src/lib/oauthContinuation.ts";

function storage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() { return values.size; },
    clear() { values.clear(); },
    getItem(key) { return values.get(key) ?? null; },
    key(i) { return [...values.keys()][i] ?? null; },
    removeItem(key) { values.delete(key); },
    setItem(key, value) { values.set(key, value); },
  };
}

test("restores only an opaque OAuth request through Microsoft redirects", () => {
  const store = storage();
  const id = "a".repeat(43);
  captureOAuthRequest(new URL(`https://qs.test/oauth/consent?request=${id}`), store);
  captureOAuthRequest(new URL("https://qs.test/?code=ms-code&state=ms-state"), store);
  assert.equal(takeOAuthReturnPath(store), `/oauth/consent?request=${id}`);
  assert.equal(takeOAuthReturnPath(store), null);
});

test("rejects arbitrary redirects, malformed and duplicate request IDs", () => {
  const store = storage();
  for (const query of ["https://evil.test/", "short", `${"a".repeat(43)}&request=${"b".repeat(43)}`]) {
    captureOAuthRequest(new URL(`https://qs.test/oauth/consent?request=${query}`), store);
    assert.equal(takeOAuthReturnPath(store), null);
  }
  store.setItem("qs_oauth_request", "//evil.test/");
  assert.equal(takeOAuthReturnPath(store), null);
});

test("preserves the consent route variants recognized by React Router", () => {
  const store = storage();
  const id = "b".repeat(43);
  captureOAuthRequest(new URL(`https://qs.test/OAUTH/CONSENT/?request=${id}`), store);
  assert.equal(takeOAuthReturnPath(store), `/oauth/consent?request=${id}`);
});
