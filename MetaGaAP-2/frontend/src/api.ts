// REST + WebSocket client for the MetaGaAP 2 backend.
import type { FsListing, Job, RunConfig, ServerInfo, WSEvent } from "./types";

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => jsonFetch<{ status: string; version: string }>("/api/health"),

  serverInfo: () => jsonFetch<ServerInfo>("/api/engines"),

  listDir: (path?: string) =>
    jsonFetch<FsListing>(`/api/fs${path ? `?path=${encodeURIComponent(path)}` : ""}`),

  createJob: (config: RunConfig) =>
    jsonFetch<Job>("/api/jobs", { method: "POST", body: JSON.stringify(config) }),

  listJobs: () => jsonFetch<Job[]>("/api/jobs"),

  getJob: (id: string) => jsonFetch<Job>(`/api/jobs/${id}`),

  cancelJob: (id: string) =>
    jsonFetch<Job>(`/api/jobs/${id}/cancel`, { method: "POST" }),

  downloadUrl: (id: string, path: string) =>
    `/api/jobs/${id}/download?path=${encodeURIComponent(path)}`,
};

/**
 * Subscribe to a job's live event stream. Returns an unsubscribe function.
 * Reconnects with simple backoff until the job reaches a terminal state or the
 * caller unsubscribes.
 */
export function subscribeJob(
  id: string,
  onEvent: (ev: WSEvent) => void,
  onStatus?: (open: boolean) => void,
): () => void {
  let socket: WebSocket | null = null;
  let closed = false;
  let retry = 0;

  const connect = () => {
    if (closed) return;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${proto}://${window.location.host}/ws/jobs/${id}`);

    socket.onopen = () => {
      retry = 0;
      onStatus?.(true);
    };
    socket.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data) as WSEvent);
      } catch {
        /* ignore malformed frame */
      }
    };
    socket.onclose = () => {
      onStatus?.(false);
      if (closed) return;
      retry = Math.min(retry + 1, 5);
      setTimeout(connect, retry * 500);
    };
    socket.onerror = () => socket?.close();
  };

  connect();
  return () => {
    closed = true;
    socket?.close();
  };
}
