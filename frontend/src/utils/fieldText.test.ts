import { describe, expect, it } from "vitest";
import { fitFieldText, wrapToWidth } from "../utils/fieldText";

const widthOf = (line: string, fontSize = 16) => line.length * fontSize * 0.5;

describe("field text fitting", () => {
  it("keeps a short answer at a size that fills the box height", () => {
    const fitted = fitFieldText("Ananya", 220, 28, false, widthOf);
    expect(fitted.fontSize).toBeGreaterThanOrEqual(16);
    expect(fitted.lines).toEqual(["Ananya"]);
    expect(fitted.padTop).toBe(0);
  });

  it("shrinks a long answer until it fits the blank", () => {
    const wide = fitFieldText("Ananya", 220, 28, false, widthOf);
    const cramped = fitFieldText("Ananya Rao", 80, 28, false, widthOf);
    expect(cramped.fontSize).toBeLessThan(wide.fontSize);
    expect(widthOf(cramped.lines[0], cramped.fontSize)).toBeLessThanOrEqual(74);
  });

  it("wraps a multiline answer and pads it toward the vertical center", () => {
    const fitted = fitFieldText("12 MG Road Bengaluru", 90, 80, true, widthOf);
    expect(fitted.lines.length).toBeGreaterThan(1);
    expect(fitted.padTop).toBeGreaterThan(0);
    for (const line of fitted.lines) {
      expect(widthOf(line, fitted.fontSize)).toBeLessThanOrEqual(84);
    }
  });

  it("wraps on word boundaries", () => {
    expect(wrapToWidth("one two three", 8, (line) => line.length)).toEqual(["one two", "three"]);
  });
});
