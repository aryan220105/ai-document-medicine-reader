interface Props {
  value: boolean;
  onChange: (value: boolean) => void;
}

export function EasyReadToggle({ value, onChange }: Props) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input
        type="checkbox"
        checked={value}
        onChange={(event) => onChange(event.target.checked)}
        aria-label="Easy Read Mode"
      />
      Easy Read Mode
    </label>
  );
}
