// Small presentation helpers for the MetaGaAP 2 UI. Pure functions, no deps.

/**
 * Join an arbitrary list of class-name fragments, dropping any that are falsey
 * (false / null / undefined / ""). Handy for conditional Tailwind classes:
 *   cls("btn", active && "btn-active", disabled && "opacity-50")
 */
export function cls(...parts: (string | false | null | undefined)[]): string {
  return parts.filter((p): p is string => Boolean(p)).join(" ");
}

/**
 * Format a fraction in the range 0..1 as a percentage string, e.g. 0.5 -> "50%".
 * Values are clamped to [0, 1] and rounded to one decimal place; trailing ".0"
 * is dropped so whole numbers read cleanly (0.5 -> "50%", 0.123 -> "12.3%").
 * Non-finite input renders as an em dash.
 */
export function fmtPct(x: number): string {
  if (!Number.isFinite(x)) return "—";
  const clamped = Math.min(1, Math.max(0, x));
  const pct = Math.round(clamped * 1000) / 10;
  const text = Number.isInteger(pct) ? String(pct) : pct.toFixed(1);
  return `${text}%`;
}

/**
 * Format an integer with locale-aware thousands separators (Australian English),
 * e.g. 1234567 -> "1,234,567". Non-integer or non-finite input renders as an em
 * dash; fractional values are rounded to the nearest integer first.
 */
export function fmtInt(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return Math.round(n).toLocaleString("en-AU");
}

/**
 * Truncate a long file-system path for display, keeping the most informative
 * trailing portion (file/dir name and its parents) and prefixing an ellipsis.
 * Splits on both "/" and "\\" so it works for Windows and POSIX paths.
 * If the path already fits within `max`, it is returned unchanged.
 */
export function shortPath(p: string, max = 48): string {
  if (!p || p.length <= max) return p;
  const parts = p.split(/[/\\]/).filter(Boolean);
  if (parts.length === 0) return p.slice(p.length - max);

  let acc = "";
  for (let i = parts.length - 1; i >= 0; i--) {
    const next = acc ? `${parts[i]}/${acc}` : parts[i];
    // Reserve room for the leading ellipsis ("…/").
    if (next.length + 2 > max) break;
    acc = next;
  }
  if (!acc) {
    // Even the final segment is too long; hard-truncate it.
    const last = parts[parts.length - 1];
    return `…${last.slice(Math.max(0, last.length - (max - 1)))}`;
  }
  return `…/${acc}`;
}
