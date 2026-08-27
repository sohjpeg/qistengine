"use client";

import { FileText, RefreshCw } from "lucide-react";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { API_BASE } from "@/lib/api";
import { cn } from "@/lib/utils";

const MAX_MB = 10;
const ACCEPT = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "text/csv": [".csv"],
  "application/json": [".json"],
};

export function FileDropzone({
  label,
  sampleName,
  onFile,
  parsedSummary,
}: {
  label: string;
  sampleName?: string;
  onFile: (file: File) => Promise<void> | void;
  parsedSummary?: { count: number; method: string } | null;
}) {
  const [state, setState] = useState<"idle" | "uploading" | "parsed" | "error">(
    parsedSummary ? "parsed" : "idle",
  );
  const [fileName, setFileName] = useState<string>("");
  const [error, setError] = useState<string>("");

  const onDrop = useCallback(
    async (accepted: File[], rejected: unknown[]) => {
      if (rejected.length) {
        setState("error");
        setError(`File must be PDF, PNG, JPG, CSV or JSON and under ${MAX_MB} MB.`);
        return;
      }
      const file = accepted[0];
      if (!file) return;
      setFileName(file.name);
      setState("uploading");
      setError("");
      try {
        await onFile(file);
        setState("parsed");
      } catch (e) {
        setState("error");
        setError(e instanceof Error ? e.message : "Could not parse the file.");
      }
    },
    [onFile],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPT,
    maxSize: MAX_MB * 1024 * 1024,
    multiple: false,
  });

  return (
    <div>
      <div
        {...getRootProps()}
        className={cn(
          "flex min-h-[132px] cursor-pointer flex-col items-center justify-center rounded-md border p-4 text-center transition-tokens",
          isDragActive
            ? "border-brand bg-brand-tint"
            : state === "parsed"
              ? "border-rule bg-surface"
              : "border-dashed border-rule-strong bg-surface-sunk",
        )}
      >
        <input {...getInputProps()} aria-label={label} />
        <FileText size={18} strokeWidth={1.5} className="text-ink-faint" aria-hidden />
        {state === "idle" && (
          <p className="mt-2 text-body text-ink-muted">
            {label} — drop a file, or click to choose
          </p>
        )}
        {state === "uploading" && (
          <>
            <p className="mt-2 text-body-strong text-ink">{fileName}</p>
            <div className="mt-2 h-1 w-40 overflow-hidden rounded-sm bg-rule">
              <div className="h-1 w-1/2 animate-pulse bg-brand" />
            </div>
          </>
        )}
        {state === "parsed" && parsedSummary && (
          <p className="mt-2 text-body text-ink">
            {parsedSummary.count} fields extracted ·{" "}
            <span
              className={cn(
                "rounded-sm px-1.5 py-px text-label uppercase",
                parsedSummary.method === "simulated"
                  ? "bg-band-medium-tint text-band-medium"
                  : "bg-band-low-tint text-band-low",
              )}
            >
              {parsedSummary.method === "simulated" ? "simulated extraction" : parsedSummary.method}
            </span>
          </p>
        )}
        {state === "error" && <p className="mt-2 text-body text-band-very-high">{error}</p>}
        {state === "parsed" && <p className="mt-1 text-caption text-ink-faint">Click to replace</p>}
      </div>
      {sampleName ? (
        <a
          href={`${API_BASE}/api/v1/samples/${sampleName}`}
          className="mt-1 inline-flex items-center gap-1 text-caption text-brand hover:underline"
        >
          <RefreshCw size={11} /> Download a sample file
        </a>
      ) : null}
    </div>
  );
}
