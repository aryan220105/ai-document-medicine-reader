export function ConfidenceBadge({ value, verify }: { value: number; verify: boolean }) {
  return (
    <span className="inline-block rounded bg-slate-100 px-2 py-1 text-xs text-slate-700">
      Confidence {Math.round(value * 100)}% heuristic
      {verify ? " — Verify with official instructions" : ""}
    </span>
  );
}
