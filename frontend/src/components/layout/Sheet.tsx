import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

/**
 * Bottom sheet on mobile, right-hand drawer from `md:` up.
 *
 * Extracted from three copy-pasted implementations (AnnotationSheet,
 * BatchAnnotationSheet, the rules editor). Adds what all of them lacked:
 * Escape-to-close, a body scroll lock, and correct behavior when one sheet
 * opens another — Escape and scrim clicks only ever dismiss the topmost sheet.
 */

// LIFO stack of open sheets. Only the last entry reacts to Escape.
const stack: symbol[] = [];
let scrollLocks = 0;

export function Sheet({
  title,
  subtitle,
  onClose,
  children,
  level = 0,
  widthClass = "md:w-[400px]",
  label,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  /** 0 = base sheet, 1 = a sheet opened from within another. */
  level?: 0 | 1;
  widthClass?: string;
  label?: string;
}) {
  const idRef = useRef<symbol>(Symbol("sheet"));

  useEffect(() => {
    const id = idRef.current;
    stack.push(id);

    // Ref-counted so a nested sheet closing doesn't unlock the page early.
    scrollLocks += 1;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (stack[stack.length - 1] !== id) return; // not the topmost sheet
      e.stopPropagation();
      onClose();
    };
    document.addEventListener("keydown", onKey);

    return () => {
      document.removeEventListener("keydown", onKey);
      const index = stack.indexOf(id);
      if (index >= 0) stack.splice(index, 1);
      scrollLocks = Math.max(0, scrollLocks - 1);
      if (scrollLocks === 0) document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  // A nested sheet sits above its parent with a lighter scrim, so the parent
  // stays visible as context instead of stacking two opaque panels.
  const scrimClass = level === 1 ? "z-[60] bg-foreground/10" : "z-40 bg-foreground/20";
  const panelZ = level === 1 ? "z-[70]" : "z-50";

  return (
    <>
      <div
        className={`fixed inset-0 backdrop-blur-[1px] ${scrimClass}`}
        onClick={onClose}
        aria-hidden
      />
      <aside
        className={
          `fixed inset-x-0 bottom-0 ${panelZ} flex max-h-[92vh] flex-col rounded-t-lg border-t ` +
          `border-border bg-background shadow-xl md:inset-y-0 md:right-0 md:left-auto ` +
          `md:max-h-none md:rounded-none md:border-l md:border-t-0 ${widthClass}`
        }
        role="dialog"
        aria-modal="true"
        aria-label={label ?? (typeof title === "string" ? title : undefined)}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-border bg-background px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{title}</div>
            {subtitle ? <div className="truncate text-xs text-muted-foreground">{subtitle}</div> : null}
          </div>
          <button
            onClick={onClose}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-secondary"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">{children}</div>
      </aside>
    </>
  );
}
