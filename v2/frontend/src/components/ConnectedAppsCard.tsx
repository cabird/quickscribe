import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { fetchConnections, revokeConnection } from "@/lib/oauth";
import { authEnabled } from "@/lib/auth";

export function ConnectedAppsCard() {
  const cache = useQueryClient();
  const apps = useQuery({ queryKey: ["oauth-connections"], queryFn: fetchConnections, enabled: authEnabled });
  const revoke = useMutation({ mutationFn: revokeConnection,
    onSuccess: () => cache.invalidateQueries({ queryKey: ["oauth-connections"] }) });
  const active = (apps.data || []).filter(app => !app.revoked_at && app.expires_at * 1000 > Date.now());
  return <Card className="space-y-3 p-5">
    <h2 className="text-sm font-semibold">Connected apps</h2>
    <p className="text-xs text-muted-foreground">Connect Claude, Codex, or another compatible app using OAuth and this server URL:</p>
    <code className="block break-all rounded bg-muted p-2 text-sm select-all">{window.location.origin}/mcp</code>
    {!authEnabled && <p className="text-sm text-muted-foreground">Sign in with Microsoft to manage connections.</p>}
    {apps.isLoading && <p className="text-sm">Loading connections…</p>}
    {(apps.error || revoke.error) && <p role="alert" className="text-sm text-destructive">{(apps.error || revoke.error)?.message}</p>}
    {apps.isSuccess && active.length === 0 && <p className="text-sm text-muted-foreground">No connected apps.</p>}
    {active.map(app => <div key={app.id} className="flex items-center gap-3 border-t pt-3">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="text-sm font-medium">{app.client_name}</div>
        <div className="break-all text-xs text-muted-foreground">{app.client_id}</div>
        <div className="text-xs text-muted-foreground">Expires {new Date(app.expires_at * 1000).toLocaleDateString()}</div>
      </div>
      <Button size="sm" variant="outline" disabled={revoke.isPending} onClick={() => revoke.mutate(app.id)}>Revoke access</Button>
    </div>)}
    {revoke.isSuccess && <p role="status" className="text-sm text-muted-foreground">Access revoked.</p>}
  </Card>;
}
