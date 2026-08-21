import { render, screen } from "@testing-library/react";
import { UploadZone } from "../components/UploadZone";
import { validateImageFile } from "../utils/validation";

describe("UploadZone", () => {
  it("renders the upload button and mode cards", () => {
    render(<UploadZone maxMb={10} onFile={() => undefined} />);
    expect(screen.getByRole("button", { name: "Upload Document" })).toBeInTheDocument();
    expect(screen.getByText("Medicine Label")).toBeInTheDocument();
    expect(screen.getByText("General Document")).toBeInTheDocument();
  });
});

describe("file validation", () => {
  it("rejects non-image files", () => {
    const file = new File(["hello"], "notes.txt", { type: "text/plain" });
    expect(validateImageFile(file)).toMatch(/PNG, JPG, JPEG, or WEBP/i);
  });
});
