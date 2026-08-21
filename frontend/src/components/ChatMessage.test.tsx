import { render, screen } from "@testing-library/react";
import { ChatMessageView } from "../components/ChatMessage";

describe("ChatMessageView", () => {
  it("renders an assistant answer with document source", () => {
    render(
      <ChatMessageView
        message={{
          id: "1",
          role: "assistant",
          text: "The expiry date appears to be DEC 2027.",
          response: {
            answer: "The expiry date appears to be DEC 2027.",
            document_sources: ["EXP DEC 2027"],
            knowledge_sources: [],
            highlights: [],
            confidence: 0.93,
            intent: "find_expiry",
            llm_used: false,
            llm_unavailable: false,
          },
        }}
      />,
    );
    expect(screen.getByText(/DEC 2027/)).toBeInTheDocument();
    expect(screen.getByText("Source: Uploaded document")).toBeInTheDocument();
  });
});
