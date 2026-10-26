export interface FittedFieldText {
  fontSize: number;
  lines: string[];
  padTop: number;
  scale: number;
}

const LINE = 1.2;
const FLOOR = 6;

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
  const max = Math.min(Math.max(boxHeight * 0.8, 1), 22);
  const sample = text.trim();
  if (boxWidth < 8 || boxHeight < 8 || !sample) {
    return { fontSize: max, lines: sample ? [sample] : [], padTop: 0, scale: 1 };
  }
  const innerWidth = Math.max(4, boxWidth - 6);
  const innerHeight = Math.max(1, boxHeight - 1);
  let size = max;
  let lines = [sample];
  const measureLines = (fontSize: number) =>
    multiline ? wrapToWidth(sample, innerWidth, (line) => widthOf(line, fontSize)) : [sample];
  while (size > FLOOR) {
    lines = measureLines(size);
    const widest = lines.reduce((widestLine, line) => Math.max(widestLine, widthOf(line, size)), 0);
    const block = lines.length * size * (multiline ? LINE : 1);
    if (widest <= innerWidth && block <= innerHeight) {
      break;
    }
    size = Math.round((size - 0.5) * 10) / 10;
  }
  lines = measureLines(size);
  const widest = lines.reduce((widestLine, line) => Math.max(widestLine, widthOf(line, size)), 0);
  const block = Math.max(lines.length, 1) * size * (multiline ? LINE : 1);
  const scale = widest > innerWidth ? innerWidth / widest : 1;
  const padTop = multiline ? Math.max(0, (boxHeight - block * scale) / 2) : 0;
  return { fontSize: size, lines, padTop, scale };
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
