import { useCallback, useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Upload, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUploadRecording } from "@/lib/queries";

interface UploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadDialog({ open, onOpenChange }: UploadDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useUploadRecording();

  const reset = useCallback(() => {
    setFile(null);
    setTitle("");
  }, []);

  const handleClose = useCallback(() => {
    if (!uploadMutation.isPending) {
      reset();
      onOpenChange(false);
    }
  }, [uploadMutation.isPending, reset, onOpenChange]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) setFile(droppedFile);
  }, []);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) setFile(selectedFile);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!file) return;

    try {
      await uploadMutation.mutateAsync({
        file,
        title: title.trim() || undefined,
      });
      reset();
      onOpenChange(false);
    } catch {
      // Error handled by mutation
    }
  }, [file, title, uploadMutation, reset, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload Audio File</DialogTitle>
          <DialogDescription>
            Upload an audio file for transcription. Supported formats: MP3, WAV, M4A, OPUS, WEBM.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Drop zone */}
          <div
            className={cn(
              "flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors",
              isDragOver
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-muted-foreground/50",
              file && "border-primary/50 bg-primary/5"
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e: React.KeyboardEvent) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            role="button"
            tabIndex={0}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,.mp3,.wav,.m4a,.opus,.webm,.ogg,.flac"
              className="hidden"
              onChange={handleFileChange}
            />

            {file ? (
              <div className="flex items-center gap-2 text-sm">
                <Upload className="h-4 w-4 text-primary" />
                <span className="font-medium">{file.name}</span>
                <span className="text-muted-foreground">
                  ({(file.size / 1024 / 1024).toFixed(1)} MB)
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                  }}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ) : (
              <>
                <Upload className="mb-2 h-8 w-8 text-muted-foreground" />
                <p className="text-sm font-medium">Drop file here or click to browse</p>
                <p className="text-xs text-muted-foreground">Audio files up to 300MB</p>
              </>
            )}
          </div>

          {/* Title input */}
          <div className="space-y-2">
            <Label htmlFor="upload-title">Title (optional)</Label>
            <Input
              id="upload-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Recording title"
              disabled={uploadMutation.isPending}
            />
          </div>

          {/* Progress */}
          {uploadMutation.isPending && (
            <div className="space-y-1">
              <Progress value={50} />
              <p className="text-center text-xs text-muted-foreground">
                Uploading...
              </p>
            </div>
          )}

          {uploadMutation.isError && (
            <p className="text-sm text-destructive">
              Upload failed. Please try again.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={uploadMutation.isPending}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!file || uploadMutation.isPending}>
            {uploadMutation.isPending ? "Uploading..." : "Upload"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
