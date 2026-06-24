// Server-side file/directory browser for the LOCAL MetaGaAP 2 app. Browses
// directories via the backend /api/fs endpoint and also accepts manual entry.
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { FsEntry, FsListing } from "../types";
import { api } from "../api";
import { cls, shortPath } from "../lib/format";

interface FilePickerProps {
  /** Currently chosen path (controlled). */
  value: string;
  /** Called with the newly chosen path. */
  onChange: (p: string) => void;
  /** Whether the picker selects a file or a directory. Defaults to "file". */
  mode?: "file" | "dir";
  /** Field label, also used for accessible naming. */
  label: string;
}

/**
 * A combined text input and pop-over directory browser. The user may type a
 * path directly or open the browser to navigate the server's file system.
 * In "dir" mode the current directory can be chosen; in "file" mode files are
 * selectable and directories are navigable.
 */
export default function FilePicker({
  value,
  onChange,
  mode = "file",
  label,
}: FilePickerProps) {
  const [open, setOpen] = useState(false);
  const [listing, setListing] = useState<FsListing | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputId = useId();
  const containerRef = useRef<HTMLDivElement>(null);

  const browse = useCallback(async (path?: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.listDir(path);
      setListing(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setListing(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load a listing whenever the browser is opened. Seed from the current value's
  // parent directory when possible, otherwise the server default root.
  useEffect(() => {
    if (!open) return;
    const seed = value ? value.replace(/[/\\][^/\\]*$/, "") : undefined;
    void browse(seed || undefined);
  }, [open, value, browse]);

  // Close the pop-over when clicking outside it.
  useEffect(() => {
    if (!open) return;
    const onDocClick = (ev: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(ev.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const handleEntry = (entry: FsEntry) => {
    if (entry.is_dir) {
      void browse(entry.path);
    } else if (mode === "file") {
      onChange(entry.path);
      setOpen(false);
    }
  };

  const chooseCurrentDir = () => {
    if (listing) {
      onChange(listing.path);
      setOpen(false);
    }
  };

  const entries = listing?.entries ?? [];

  return (
    <div className="flex flex-col gap-1" ref={containerRef}>
      <label htmlFor={inputId} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="relative flex gap-2">
        <input
          id={inputId}
          type="text"
          value={value}
          spellCheck={false}
          autoComplete="off"
          placeholder={mode === "dir" ? "Select a directory…" : "Select a file…"}
          onChange={(e) => onChange(e.target.value)}
          className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
        />
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-haspopup="dialog"
          aria-label={`Browse for ${label}`}
          className="shrink-0 rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
        >
          Browse…
        </button>

        {open && (
          <div
            role="dialog"
            aria-label={`Browse ${label}`}
            className="absolute left-0 top-full z-20 mt-1 flex max-h-80 w-full min-w-80 flex-col overflow-hidden rounded-md border border-slate-300 bg-white shadow-lg"
          >
            <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2">
              <button
                type="button"
                disabled={!listing?.parent}
                onClick={() => listing?.parent && void browse(listing.parent)}
                className="rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                aria-label="Go to parent directory"
              >
                ↑ Up
              </button>
              <span
                className="min-w-0 flex-1 truncate text-xs text-slate-500"
                title={listing?.path ?? ""}
              >
                {listing ? shortPath(listing.path, 40) : "…"}
              </span>
            </div>

            <ul className="min-h-0 flex-1 overflow-y-auto py-1">
              {loading && (
                <li className="px-3 py-2 text-sm text-slate-400">Loading…</li>
              )}
              {error && !loading && (
                <li className="px-3 py-2 text-sm text-rose-600">{error}</li>
              )}
              {!loading && !error && entries.length === 0 && (
                <li className="px-3 py-2 text-sm text-slate-400">Empty directory</li>
              )}
              {!loading &&
                !error &&
                entries.map((entry) => {
                  const selectable = entry.is_dir || mode === "file";
                  return (
                    <li key={entry.path}>
                      <button
                        type="button"
                        disabled={!selectable}
                        onClick={() => handleEntry(entry)}
                        className={cls(
                          "flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm",
                          selectable
                            ? "text-slate-800 hover:bg-sky-50"
                            : "cursor-not-allowed text-slate-400",
                        )}
                      >
                        <span aria-hidden="true">{entry.is_dir ? "📁" : "📄"}</span>
                        <span className="min-w-0 flex-1 truncate">{entry.name}</span>
                      </button>
                    </li>
                  );
                })}
            </ul>

            {mode === "dir" && (
              <div className="border-t border-slate-200 bg-slate-50 px-3 py-2">
                <button
                  type="button"
                  disabled={!listing}
                  onClick={chooseCurrentDir}
                  className="w-full rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Select this directory
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
