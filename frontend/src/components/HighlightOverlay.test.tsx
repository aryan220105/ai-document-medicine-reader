import { render } from "@testing-library/react";
import { HighlightOverlay } from "../components/HighlightOverlay";

describe("HighlightOverlay", () => {
  it("positions boxes with percentage coordinates", () => {
    const { getByTestId } = render(
      <HighlightOverlay
        highlights={[{ x: 0.62, y: 0.71, width: 0.14, height: 0.05, label: "Expiry Date" }]}
      />,
    );
    const overlay = getByTestId("highlight-overlay");
    const box = overlay.firstElementChild as HTMLElement;
    expect(box.style.left).toBe("62%");
    expect(box.style.top).toBe("71%");
    expect(box.style.width).toBe("14%");
    expect(box.style.height).toBe("5%");
  });
});
