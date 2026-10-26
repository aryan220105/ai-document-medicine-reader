export interface FittedFieldText {
  fontSize: number;
  lines: string[];
  padTop: number;
}

const MIN_FONT = 10;
const LINE = 1.2;

export function wrapToWidth(text: string, maxWidth: number, widthOf: (line: string) => number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length === 0) {
    return [];
  }
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const trial = current ? `${current} ${word}` : word;
    if (widthOf(trial) <= maxWidth || !current) {
      current = trial;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) {
    lines.push(current);
  }
  return lines;
}

export function fitFieldText(
  text: string,
  boxWidth: number,
  boxHeight: number,
  multiline: boolean,
  widthOf: (line: string, fontSize: number) => number,
): FittedFieldText {
  const max = Math.min(Math.max(boxHeight * 0.72, MIN_FONT), 22);
  if (boxWidth < 8 || boxHeight < 8) {
    return { fontSize: max, lines: text ? [text] : [], padTop: 0 };
  }
  const sample = text.trim();
  const innerWidth = Math.max(4, boxWidth - 6);
  let size = max;
  let lines = sample ? [sample] : [];
  while (size > MIN_FONT) {
    lines = sample
      ? multiline
        ? wrapToWidth(sample, innerWidth, (line) => widthOf(line, size))
        : [sample]
      : [];
    const widest = lines.reduce((widestLine, line) => Math.max(widestLine, widthOf(line, size)), 0);
    const block = Math.max(lines.length, 1) * size * (multiline ? LINE : 1);
    if (widest <= innerWidth && block <= boxHeight - 1) {
      break;
    }
    size = Math.round((size - 0.5) * 10) / 10;
  }
  const block = Math.max(lines.length, 1) * size * (multiline ? LINE : 1);
  const padTop = multiline ? Math.max(0, (boxHeight - block) / 2) : 0;
  return { fontSize: size, lines, padTop };
}

export function measureTextWidth(line: string, fontSize: number): number {
  if (typeof document === "undefined") {
    return line.length * fontSize * 0.55;
  }
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) {
    return line.length * fontSize * 0.55;
  }
  context.font = `600 ${fontSize}px Outfit, "Segoe UI", sans-serif`;
  return context.measureText(line).width;
}
