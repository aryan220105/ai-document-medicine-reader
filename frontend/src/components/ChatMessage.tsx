import type { ChatMessage } from "../types";

interface Props {
  message: ChatMessage;
}

export function ChatMessageView({ message }: Props) {
  const isUser = message.role === "user";
  const sources = message.response;
  return (
    <article className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[92%] rounded-2xl px-4 py-3 ${isUser ? "bg-moss text-white" : "bg-paper"}`}>
        <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
        {!isUser && sources ? (
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {sources.document_sources.length ? (
              <span className="rounded-full bg-white px-2 py-1">Source: Uploaded document</span>
            ) : null}
            {sources.knowledge_sources.length ? (
              <span className="rounded-full bg-white px-2 py-1">Source: Knowledge Base</span>
            ) : null}
            {sources.confidence > 0 ? (
              <span className="rounded-full bg-white px-2 py-1">Confidence {Math.round(sources.confidence * 100)}%</span>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}
