/** Uniform 0–3 historical-line control shared by any comparison-capable chart. */
export function PriorPeriodsControl({ value, onChange }: {
  value: number; onChange: (count: number) => void;
}) {
  return (
    <div className="flex shrink-0 items-center gap-1.5" role="group" aria-label="Prior periods">
      <span className="text-[11px] text-muted-foreground">Prior</span>
      <div className="inline-flex overflow-hidden rounded-md border border-input" aria-label="Historical comparison count">
        {[0, 1, 2, 3].map((count) => (
          <button key={count} type="button" aria-label={count + " prior periods"}
            aria-pressed={value === count} onClick={() => onChange(count)}
            className={"min-w-7 px-2 py-1.5 text-xs font-medium transition-colors " +
              (value === count ? "bg-primary text-primary-foreground" : "bg-card hover:bg-secondary")}>
            {count}
          </button>
        ))}
      </div>
    </div>
  );
}
