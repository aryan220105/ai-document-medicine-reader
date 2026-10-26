import type { FormContext } from "../types";

interface Props {
  context: FormContext | null | undefined;
}

/**
 * What FormSathi understood the document to be, shown before the field list.
 *
 * Worth surfacing because it is what every field description rests on. If the glossary
 * says "AC = Assembly Constituency", the fields captioned "AC No." are explained as
 * constituency numbers; if it were wrong, every one of those descriptions would be wrong
 * in the same way, and the user should be able to see that at a glance rather than infer
 * it from a run of odd answers.
 */
export function FormContextNote({ context }: Props) {
  if (!context || (!context.title && !context.authority && !Object.keys(context.glossary ?? {}).length)) {
    return null;
  }
  const terms = Object.entries(context.glossary ?? {});
  return (
    <details className="mt-2 rounded-xl border border-softline bg-foam p-2 text-xs" data-testid="form-context">
      <summary className="cursor-pointer font-medium text-ink">
        {context.title || "This form"}
        {context.authority ? ` — ${context.authority}` : ""}
      </summary>
      {context.purpose ? <p className="mt-1 text-pine">{context.purpose}</p> : null}
      {terms.length ? (
        <>
          <p className="mt-2 font-medium text-ink">Abbreviations on this form</p>
          <ul className="mt-1 space-y-0.5">
            {terms.map(([term, meaning]) => (
              <li key={term}>
                <span className="font-medium">{term}</span> — {meaning}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {context.notes?.length ? (
        <>
          <p className="mt-2 font-medium text-ink">From the form's own instructions</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {context.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </>
      ) : null}
      {context.web_sources?.length ? (
        <>
          <p className="mt-2 font-medium text-ink">Background looked up online</p>
          <p className="mt-1 text-pine">
            Used only to fill gaps this document left, such as an abbreviation it never spells out. Anything printed on
            your form takes precedence.
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {context.web_sources.map((source) => (
              <li key={source}>{source}</li>
            ))}
          </ul>
        </>
      ) : null}
      <p className="mt-2 text-pine/75">Read from this document. Always check the form's own instructions.</p>
    </details>
  );
}
