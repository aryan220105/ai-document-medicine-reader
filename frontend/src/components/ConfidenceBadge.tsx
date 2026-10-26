export function ConfidenceBadge({ value, verify }: { value: number; verify: boolean }) {
  return (
    <span className="fs-chip bg-white text-pine ring-1 ring-softline">
      Confidence {Math.round(value * 100)}% heuristic
      {verify ? " — Verify with official instructions" : ""}
    </span>
  );
}
