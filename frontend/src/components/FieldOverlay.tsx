import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { fitFieldText, measureTextWidth, type FittedFieldText } from "../utils/fieldText";
import { overlayStyle, validateAnswer } from "../utils/validation";
import type { DetectedField } from "../types";

interface Props {
  field: DetectedField;
  active: boolean;
  completed: boolean;
  value: string;
  onSelect: (id: string) => void;
  onChange: (id: string, value: string) => void;
}

function canType(field: DetectedField): boolean {
  if (field.field_type === "signature" || field.field_type === "checkbox" || field.field_type === "radio") {
    return false;
  }
  if (field.filled_by === "office" || field.validation_rule?.kind === "office_use") {
    return false;
  }
  return true;
}

export function FieldOverlay({ field, active, completed, value, onSelect, onChange }: Props) {
  const low = field.confidence < 0.55;
  const typing = canType(field);
  const choice = field.field_type === "checkbox" || field.field_type === "radio";
  const inputRef = useRef<HTMLInputElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState<FittedFieldText>({ fontSize: 14, lines: [], padTop: 0, scale: 1 });
  const [boxHeight, setBoxHeight] = useState(0);
  const error = typing ? validateAnswer(field, value) : null;
  const multiline = field.field_type === "multiline";
  const color = active
    ? "border-coral bg-coral/15 ring-2 ring-coral/30"
    : completed
      ? "border-leaf bg-leaf/10"
      : low
        ? "border-red-700 bg-red-500/10"
        : "border-leaf/70 bg-leaf/10 hover:bg-leaf/15";

  useEffect(() => {
    if (active && typing) {
      (inputRef.current ?? areaRef.current)?.focus();
    }
  }, [active, typing, field.id]);

  useLayoutEffect(() => {
    const node = boxRef.current;
    if (!node) {
      return;
    }
    const measure = () => {
      const width = node.clientWidth;
      const height = node.clientHeight;
      setBoxHeight(height);
      setFit(fitFieldText(value, width, height, multiline, measureTextWidth));
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [value, multiline, active]);

  const label = field.label || field.id;

  const inkStyle = {
    fontSize: fit.fontSize,
    textAlign: "center" as const,
    lineHeight: multiline ? 1.2 : boxHeight > 0 ? `${boxHeight}px` : undefined,
    paddingTop: multiline ? fit.padTop : 0,
    transform: fit.scale < 0.995 ? `scale(${fit.scale})` : undefined,
    transformOrigin: "center center",
  };

  return (
    <div ref={boxRef} className={`field-ink absolute border-2 transition ${color}`} style={overlayStyle(field.input_box)}>
      {typing && active ? (
        multiline ? (
          <textarea
            ref={areaRef}
            aria-label={label}
            className="field-ink-input"
            value={value}
            dir="auto"
            style={inkStyle}
            aria-invalid={error ? true : undefined}
            onChange={(event) => onChange(field.id, event.target.value)}
          />
        ) : (
          <input
            ref={inputRef}
            aria-label={label}
            className="field-ink-input"
            value={value}
            dir="auto"
            style={inkStyle}
            aria-invalid={error ? true : undefined}
            onChange={(event) => onChange(field.id, event.target.value)}
          />
        )
      ) : (
        <button
          type="button"
          aria-label={label}
          aria-pressed={choice ? value === "true" : undefined}
          className="field-ink-button"
          onClick={() => {
            onSelect(field.id);
            if (choice && field.filled_by !== "office") {
              onChange(field.id, value === "true" ? "" : "true");
            }
          }}
        >
          <span
            className="field-ink-value"
            style={{
              fontSize: choice ? Math.max(boxHeight * 0.7, 12) : fit.fontSize,
              transform: !choice && fit.scale < 0.995 ? `scale(${fit.scale})` : undefined,
              whiteSpace: fit.lines.length > 1 ? "pre-wrap" : "nowrap",
            }}
          >
            {choice ? (value === "true" ? "✓" : "") : fit.lines.join("\n")}
          </span>
        </button>
      )}
    </div>
  );
}
