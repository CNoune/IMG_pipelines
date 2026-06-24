// Horizontal step indicator for the run wizard. Accessible (aria-current).
import { cls } from "../lib/format";

interface StepperProps {
  steps: string[];
  /** Zero-based index of the active step. */
  current: number;
}

/**
 * Render a horizontal sequence of numbered steps. Completed steps show a tick,
 * the active step is highlighted and carries aria-current="step", and upcoming
 * steps are dimmed. The list is exposed as an ordered navigation landmark so
 * assistive tech can announce progress through the wizard.
 */
export default function Stepper({ steps, current }: StepperProps) {
  return (
    <nav aria-label="Pipeline steps">
      <ol className="flex w-full items-center gap-2">
        {steps.map((label, i) => {
          const isActive = i === current;
          const isDone = i < current;
          const isLast = i === steps.length - 1;
          return (
            <li
              key={label}
              className="flex flex-1 items-center gap-2 last:flex-none"
              aria-current={isActive ? "step" : undefined}
            >
              <span
                className={cls(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-semibold transition-colors",
                  isActive && "border-sky-600 bg-sky-600 text-white",
                  isDone && "border-emerald-600 bg-emerald-600 text-white",
                  !isActive && !isDone && "border-slate-300 bg-white text-slate-400",
                )}
                aria-hidden="true"
              >
                {isDone ? "✓" : i + 1}
              </span>
              <span
                className={cls(
                  "whitespace-nowrap text-sm font-medium",
                  isActive && "text-sky-700",
                  isDone && "text-emerald-700",
                  !isActive && !isDone && "text-slate-400",
                )}
              >
                {label}
              </span>
              {!isLast && (
                <span
                  className={cls(
                    "mx-1 hidden h-px flex-1 sm:block",
                    isDone ? "bg-emerald-500" : "bg-slate-200",
                  )}
                  aria-hidden="true"
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
