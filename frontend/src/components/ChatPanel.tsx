import { FormEvent, useState } from "react";
import type { ChatMessage } from "../types";
import { ChatMessageView } from "./ChatMessage";

interface Props {
  messages: ChatMessage[];
  suggestions: string[];
  busy: boolean;
  onAsk: (question: string) => Promise<void>;
  onExplainSimply: () => Promise<void>;
}

export function ChatPanel({ messages, suggestions, busy, onAsk, onExplainSimply }: Props) {
  const [question, setQuestion] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = question.trim();
    if (!value) {
      return;
    }
    setQuestion("");
    await onAsk(value);
  }

  return (
    <section className="flex h-full min-h-[28rem] flex-col rounded-2xl border border-sand bg-white p-4">
      <h2 className="font-serif text-xl">AI Assistant</h2>
      <div className="mt-4 flex-1 space-y-3 overflow-auto">
        {messages.length === 0 ? (
          <p className="text-slate-600">Ask a question about the uploaded document. Suggested questions are below.</p>
        ) : (
          messages.map((message) => <ChatMessageView key={message.id} message={message} />)
        )}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {suggestions.map((item) => (
          <button
            key={item}
            type="button"
            className="rounded-full border border-sand px-3 py-2 text-left text-sm hover:bg-paper"
            onClick={() => onAsk(item)}
            disabled={busy}
          >
            {item}
          </button>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-full bg-ink px-4 py-2 text-white disabled:opacity-50"
          onClick={onExplainSimply}
          disabled={busy}
        >
          Explain Simply
        </button>
      </div>
      <form className="mt-3 flex gap-2" onSubmit={submit}>
        <label className="sr-only" htmlFor="question">
          Ask a question
        </label>
        <textarea
          id="question"
          className="min-h-[3rem] flex-1 rounded-2xl border border-sand p-3"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about this document"
        />
        <button type="submit" className="rounded-2xl bg-moss px-4 py-2 font-semibold text-white disabled:opacity-50" disabled={busy}>
          Ask
        </button>
      </form>
    </section>
  );
}
