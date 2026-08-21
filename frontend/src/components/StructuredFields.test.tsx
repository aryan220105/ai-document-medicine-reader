import { render, screen } from "@testing-library/react";
import { StructuredFields } from "../components/StructuredFields";
import type { DetectedField } from "../types";

const fields: DetectedField[] = [
  {
    field_type: "expiry_date",
    value: "DEC 2027",
    confidence: 0.9,
    word_ids: [1],
    bounding_boxes: [],
    uncertain: false,
    label: "Expiry",
  },
];

describe("StructuredFields", () => {
  it("renders detected field values", () => {
    render(<StructuredFields fields={fields} />);
    expect(screen.getByText("Expiry")).toBeInTheDocument();
    expect(screen.getByText("DEC 2027")).toBeInTheDocument();
  });
});
