import { useCallback, useEffect, useState } from "react";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Eye, EyeOff, HelpCircle, Loader2, Pencil, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import * as api from "@/lib/api";
import {
  useCurrentUser,
  useUpdateSettings,
  useAnalysisTemplates,
  useCreateAnalysisTemplate,
  useUpdateAnalysisTemplate,
  useDeleteAnalysisTemplate,
} from "@/lib/queries";
import type { AnalysisTemplate, UserProfile } from "@/types/models";

export default function SettingsPage() {
  const { data: user } = useCurrentUser();

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-2xl space-y-6 p-4 md:p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>

        {/* Profile card */}
        {user && <ProfileCard user={user} />}

        {/* Plaud integration */}
        {user && <PlaudCard user={user} />}

        {/* Speaker Profiles */}
        <SpeakerProfilesCard />

        {/* Analysis templates */}
        <AnalysisTemplatesSection />
      </div>
    </ScrollArea>
  );
}

function ProfileCard({ user }: { user: UserProfile }) {
  return (
    <Card className="p-5">
      <h2 className="text-sm font-semibold">Profile</h2>
      <Separator className="my-3" />
      <div className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
        <InfoRow label="Name" value={user.name} />
        <InfoRow label="Email" value={user.email} />
        <InfoRow
          label="Member Since"
          value={
            user.created_at
              ? format(new Date(user.created_at), "PP")
              : "-"
          }
        />
        <InfoRow label="User ID" value={user.id} />
      </div>
    </Card>
  );
}

function PlaudCard({ user }: { user: UserProfile }) {
  const [plaudEnabled, setPlaudEnabled] = useState(user.plaud_enabled);
  const [plaudToken, setPlaudToken] = useState(
    user.plaud_token ?? ""
  );
  const [showToken, setShowToken] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  const updateSettingsMutation = useUpdateSettings();

  useEffect(() => {
    setPlaudEnabled(user.plaud_enabled);
    setPlaudToken(user.plaud_token ?? "");
    setIsDirty(false);
  }, [user]);

  const handleToggle = useCallback(
    (checked: boolean) => {
      setPlaudEnabled(checked);
      setIsDirty(
        checked !== user.plaud_enabled ||
          plaudToken !== (user.plaud_token ?? "")
      );
    },
    [user, plaudToken]
  );

  const handleTokenChange = useCallback(
    (value: string) => {
      setPlaudToken(value);
      setIsDirty(
        plaudEnabled !== user.plaud_enabled ||
          value !== (user.plaud_token ?? "")
      );
    },
    [user, plaudEnabled]
  );

  const handleSave = useCallback(async () => {
    await updateSettingsMutation.mutateAsync({
      plaud_enabled: plaudEnabled,
      plaud_token: plaudToken,
    });
    setIsDirty(false);
  }, [plaudEnabled, plaudToken, updateSettingsMutation]);

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold">Plaud Integration</h2>
        <Dialog>
          <DialogTrigger render={<Button variant="ghost" size="icon" className="h-5 w-5 text-muted-foreground hover:text-primary" title="How to get your Plaud token" />}>
              <HelpCircle className="h-4 w-4" />
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>How to Get Your Plaud Bearer Token</DialogTitle>
              <DialogDescription>Follow these 4 steps to extract your token from the Plaud web app.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 text-sm">
              <div>
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">1</span>
                  <span className="font-semibold">Open the Plaud web app</span>
                </div>
                <p className="ml-8 mt-1 text-muted-foreground">Go to <strong>web.plaud.ai</strong> and log in with your account.</p>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">2</span>
                  <span className="font-semibold">Open the browser console</span>
                </div>
                <p className="ml-8 mt-1 text-muted-foreground">Press <strong>F12</strong> (or right-click → Inspect → Console tab).</p>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">3</span>
                  <span className="font-semibold">Run this command</span>
                </div>
                <p className="ml-8 mt-1 text-muted-foreground">Paste the following into the console and press Enter:</p>
                <code className="ml-8 mt-1 block rounded bg-muted px-3 py-2 font-mono text-xs">localStorage.getItem('tokenstr')</code>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">4</span>
                  <span className="font-semibold">Copy the token</span>
                </div>
                <p className="ml-8 mt-1 text-muted-foreground">The output will look like <strong>bearer eyJhbG...</strong> — copy everything <em>after</em> "bearer " (just the eyJ... part) and paste it into the Bearer Token field.</p>
              </div>
              <div className="rounded-md bg-amber-50 p-3 text-xs text-amber-800">
                <strong>Note:</strong> Tokens expire periodically. If you see a "401 Unauthorized" error in the job logs, repeat these steps for a fresh token.
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <Separator className="my-3" />

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <Label>Enable Plaud Sync</Label>
            <p className="text-xs text-muted-foreground">
              Automatically sync recordings from your Plaud device
            </p>
          </div>
          <Switch
            checked={plaudEnabled}
            onCheckedChange={handleToggle}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="plaud-token">Bearer Token</Label>
          <div className="relative">
            <Input
              id="plaud-token"
              type={showToken ? "text" : "password"}
              value={plaudToken}
              onChange={(e) => handleTokenChange(e.target.value)}
              placeholder="Enter your Plaud bearer token"
              className="pr-10"
            />
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2"
              onClick={() => setShowToken(!showToken)}
            >
              {showToken ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        {user.plaud_last_sync && (
          <p className="text-xs text-muted-foreground">
            Last sync:{" "}
            {format(new Date(user.plaud_last_sync), "PPp")}
          </p>
        )}

        <Button
          onClick={handleSave}
          disabled={!isDirty || updateSettingsMutation.isPending}
          className="gap-1"
        >
          <Save className="h-4 w-4" />
          {updateSettingsMutation.isPending ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </Card>
  );
}

function SpeakerProfilesCard() {
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleRebuild = useCallback(async () => {
    setIsRebuilding(true);
    setResult(null);
    try {
      const res = await api.rebuildSpeakerProfiles();
      setResult(res.message || "Profiles rebuilt successfully");
    } catch {
      setResult("Failed to rebuild profiles");
    } finally {
      setIsRebuilding(false);
    }
  }, []);

  return (
    <Card className="p-5">
      <h2 className="text-sm font-semibold">Speaker Identification</h2>
      <Separator className="my-3" />
      <p className="mb-3 text-sm text-muted-foreground">
        Rebuild speaker voice profiles from all manually verified speaker
        assignments across your recordings. This is useful after migration or if
        profiles seem inaccurate.
      </p>
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={handleRebuild}
          disabled={isRebuilding}
        >
          {isRebuilding ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Rebuild Speaker Profiles
        </Button>
        {result && (
          <span className="text-sm text-muted-foreground">{result}</span>
        )}
      </div>
    </Card>
  );
}

function AnalysisTemplatesSection() {
  const { data: templatesData } = useAnalysisTemplates();
  const templates: AnalysisTemplate[] = templatesData ?? [];

  const [editingId, setEditingId] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [editName, setEditName] = useState("");
  const [editPrompt, setEditPrompt] = useState("");

  const createMutation = useCreateAnalysisTemplate();
  const updateMutation = useUpdateAnalysisTemplate();
  const deleteMutation = useDeleteAnalysisTemplate();

  const startEdit = useCallback((template: AnalysisTemplate) => {
    setEditingId(template.id);
    setEditName(template.name);
    setEditPrompt(template.prompt);
    setShowNew(false);
  }, []);

  const startNew = useCallback(() => {
    setEditingId(null);
    setEditName("");
    setEditPrompt("");
    setShowNew(true);
  }, []);

  const handleSave = useCallback(async () => {
    if (!editName.trim() || !editPrompt.trim()) return;

    if (editingId) {
      await updateMutation.mutateAsync({
        id: editingId,
        body: { name: editName.trim(), prompt: editPrompt.trim() },
      });
    } else {
      await createMutation.mutateAsync({
        name: editName.trim(),
        prompt: editPrompt.trim(),
      });
    }
    setEditingId(null);
    setShowNew(false);
  }, [editingId, editName, editPrompt, createMutation, updateMutation]);

  const handleDelete = useCallback(
    async (id: string) => {
      await deleteMutation.mutateAsync(id);
      if (editingId === id) {
        setEditingId(null);
      }
    },
    [deleteMutation, editingId]
  );

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Analysis Templates</h2>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1"
          onClick={startNew}
        >
          <Plus className="h-3.5 w-3.5" />
          Add
        </Button>
      </div>
      <Separator className="my-3" />

      <div className="space-y-3">
        {templates.map((template) =>
          editingId === template.id ? (
            <TemplateEditor
              key={template.id}
              name={editName}
              prompt={editPrompt}
              onNameChange={setEditName}
              onPromptChange={setEditPrompt}
              onSave={handleSave}
              onCancel={() => setEditingId(null)}
              isSaving={updateMutation.isPending}
            />
          ) : (
            <div
              key={template.id}
              className="flex items-start justify-between rounded-md border p-3"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{template.name}</p>
                <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                  {template.prompt}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1 ml-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => startEdit(template)}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger
                    className="inline-flex h-7 w-7 items-center justify-center rounded-md text-destructive hover:bg-accent"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete template?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Delete &quot;{template.name}&quot;? This cannot be
                        undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => handleDelete(template.id)}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          )
        )}

        {showNew && (
          <TemplateEditor
            name={editName}
            prompt={editPrompt}
            onNameChange={setEditName}
            onPromptChange={setEditPrompt}
            onSave={handleSave}
            onCancel={() => setShowNew(false)}
            isSaving={createMutation.isPending}
          />
        )}

        {templates.length === 0 && !showNew && (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No analysis templates yet. Create one to analyze transcripts with
            custom prompts.
          </p>
        )}
      </div>
    </Card>
  );
}

function TemplateEditor({
  name,
  prompt,
  onNameChange,
  onPromptChange,
  onSave,
  onCancel,
  isSaving,
}: {
  name: string;
  prompt: string;
  onNameChange: (v: string) => void;
  onPromptChange: (v: string) => void;
  onSave: () => void;
  onCancel: () => void;
  isSaving: boolean;
}) {
  return (
    <div className="space-y-3 rounded-md border bg-muted/20 p-3">
      <div className="space-y-2">
        <Label>Template Name</Label>
        <Input
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="e.g. Meeting Summary"
          disabled={isSaving}
        />
      </div>
      <div className="space-y-2">
        <Label>Prompt</Label>
        <Textarea
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder="Write your prompt here. Use {transcript} as a placeholder for the transcript text."
          className="min-h-[100px] font-mono text-sm"
          disabled={isSaving}
        />
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button
          size="sm"
          onClick={onSave}
          disabled={!name.trim() || !prompt.trim() || isSaving}
        >
          {isSaving ? "Saving..." : "Save"}
        </Button>
      </div>
    </div>
  );
}

function InfoRow({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div>
      <span className="text-muted-foreground">{label}</span>
      <p className="font-medium">{value || "-"}</p>
    </div>
  );
}
