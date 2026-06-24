// Read-only environment report for MetaGaAP 2. Shows each detected compute
// engine (portable / native) with its availability and supported aligners and
// callers, then a table of external tools (name / version / found). The engine
// nominated as the server default is highlighted.
import type { EngineCapabilities, ServerInfo, ToolInfo } from "../types";
import { cls } from "../lib/format";

interface EngineStatusProps {
  /** Server capability report, or null while still loading. */
  info: ServerInfo | null;
}

/** Friendly, capitalised label for an aligner / caller key, e.g. "bwa_mem2"
 *  -> "bwa mem2". Falls back to the raw key for anything unexpected. */
function prettyKey(key: string): string {
  return key.replace(/_/g, " ");
}

/** A small coloured availability pill. */
function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={cls(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold",
        ok
          ? "bg-emerald-100 text-emerald-800"
          : "bg-rose-100 text-rose-800",
      )}
    >
      <span aria-hidden="true">{ok ? "●" : "○"}</span>
      {label}
    </span>
  );
}

/** A single capability chip (aligner or caller name). */
function Chip({ children }: { children: string }) {
  return (
    <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
      {children}
    </span>
  );
}

function EngineCard({
  engine,
  isDefault,
}: {
  engine: EngineCapabilities;
  isDefault: boolean;
}) {
  return (
    <div
      className={cls(
        "flex flex-col gap-3 rounded-xl border p-4 shadow-sm transition-colors",
        isDefault
          ? "border-sky-400 bg-sky-50/60 ring-1 ring-sky-300"
          : "border-slate-200 bg-white",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col">
          <span className="text-base font-semibold text-slate-900">
            {engine.label}
          </span>
          <span className="text-xs font-mono text-slate-400">{engine.key}</span>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Badge
            ok={engine.available}
            label={engine.available ? "Available" : "Unavailable"}
          />
          {isDefault && (
            <span className="inline-flex items-center rounded-full bg-sky-600 px-2.5 py-0.5 text-xs font-semibold text-white">
              Default
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2 text-sm">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Aligners
          </span>
          <div className="flex flex-wrap gap-1.5">
            {engine.aligners.length > 0 ? (
              engine.aligners.map((a) => <Chip key={a}>{prettyKey(a)}</Chip>)
            ) : (
              <span className="text-xs text-slate-400">None</span>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Variant callers
          </span>
          <div className="flex flex-wrap gap-1.5">
            {engine.callers.length > 0 ? (
              engine.callers.map((c) => <Chip key={c}>{prettyKey(c)}</Chip>)
            ) : (
              <span className="text-xs text-slate-400">None</span>
            )}
          </div>
        </div>
      </div>

      {engine.missing.length > 0 && (
        <div className="flex flex-col gap-1 rounded-md bg-amber-50 p-2">
          <span className="text-xs font-semibold text-amber-800">
            Missing tools
          </span>
          <div className="flex flex-wrap gap-1.5">
            {engine.missing.map((m) => (
              <span
                key={m}
                className="inline-flex items-center rounded-md bg-amber-100 px-2 py-0.5 font-mono text-xs text-amber-800"
              >
                {m}
              </span>
            ))}
          </div>
        </div>
      )}

      {engine.note && (
        <p className="text-xs text-slate-500">{engine.note}</p>
      )}
    </div>
  );
}

function ToolsTable({ tools }: { tools: ToolInfo[] }) {
  if (tools.length === 0) {
    return (
      <p className="text-sm text-slate-400">No external tools were probed.</p>
    );
  }
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">Detected external tools</caption>
        <thead>
          <tr className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <th scope="col" className="px-3 py-2">
              Tool
            </th>
            <th scope="col" className="px-3 py-2">
              Version
            </th>
            <th scope="col" className="px-3 py-2 text-right">
              Found
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tools.map((tool) => (
            <tr key={tool.name} className="bg-white">
              <td className="px-3 py-2">
                <span className="font-mono font-medium text-slate-800">
                  {tool.name}
                </span>
                {tool.path && (
                  <span
                    className="block truncate text-xs text-slate-400"
                    title={tool.path}
                  >
                    {tool.path}
                  </span>
                )}
              </td>
              <td className="px-3 py-2 text-slate-600">
                {tool.version ?? <span className="text-slate-400">—</span>}
              </td>
              <td className="px-3 py-2 text-right">
                <Badge ok={tool.found} label={tool.found ? "Yes" : "No"} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Render the server's environment report: one card per compute engine showing
 * availability and supported aligners / callers, followed by a table of probed
 * external tools. The default engine is visually emphasised. While the report
 * is loading (`info` is null) a placeholder message is shown.
 */
export default function EngineStatus({ info }: EngineStatusProps) {
  if (!info) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-400">
        Detecting engines and tools…
      </div>
    );
  }

  return (
    <section className="flex flex-col gap-6" aria-label="Engine status">
      <header className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold text-slate-900">Compute engines</h2>
        <p className="text-sm text-slate-500">
          MetaGaAP 2 detected the following engines on this machine. The portable
          engine runs everywhere with no external tools; the native engine uses
          installed binaries where available.
        </p>
        <dl className="mt-1 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
          <div className="flex gap-1">
            <dt className="font-semibold">Version</dt>
            <dd className="font-mono">{info.version}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="font-semibold">Platform</dt>
            <dd className="font-mono">{info.platform}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="font-semibold">Python</dt>
            <dd className="font-mono">{info.python}</dd>
          </div>
        </dl>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        {info.engines.map((engine) => (
          <EngineCard
            key={engine.key}
            engine={engine}
            isDefault={engine.key === info.default_engine}
          />
        ))}
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-base font-semibold text-slate-900">External tools</h3>
        <ToolsTable tools={info.tools} />
      </div>
    </section>
  );
}
