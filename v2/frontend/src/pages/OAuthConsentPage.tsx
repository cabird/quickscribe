import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { decideConsent, fetchConsent, type ConsentInfo } from "@/lib/oauth";

export default function OAuthConsentPage() {
  const [params] = useSearchParams();
  const id = params.get("request") || "";
  const [info, setInfo] = useState<ConsentInfo | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    fetchConsent(id).then(data => { if (active) setInfo(data); })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [id]);

  async function decide(decision: "approve" | "deny") {
    if (!info) return;
    setBusy(true);
    setError("");
    try {
      const result = await decideConsent(id, info.csrf, decision);
      window.location.assign(result.redirect_uri);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to complete the request.");
      setBusy(false);
    }
  }

  return <main className="flex min-h-screen items-center justify-center bg-background p-4">
    <Card className="w-full max-w-lg space-y-5 p-7">
      <div className="text-sm font-semibold text-primary">QuickScribe</div>
      <h1 className="text-2xl font-semibold">{info ? `Connect ${info.client_name}?` : "Connect to QuickScribe"}</h1>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {!info && !error && <p>Loading connection request…</p>}
      {info && <>
        <p className="break-words text-sm">Signed in as <strong>{info.email || info.name}</strong></p>
        <div className="space-y-2 text-sm">
          <p>This app will be able to:</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>Search and read your recordings, transcripts, summaries, meeting notes, people, and tags.</li>
            <li>Ask AI questions about your recordings.</li>
          </ul>
          <p className="text-muted-foreground">Access lasts up to 90 days. You can revoke it in Settings → Connected apps.</p>
        </div>
        <div className="space-y-1 break-all text-xs text-muted-foreground">
          <p>Client: {info.client_id}</p>
          <p>Return to: {info.redirect_uri}</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" disabled={busy} onClick={() => decide("deny")}>Cancel</Button>
          <Button disabled={busy} onClick={() => decide("approve")}>{busy ? "Connecting…" : "Allow access"}</Button>
        </div>
      </>}
    </Card>
  </main>;
}
