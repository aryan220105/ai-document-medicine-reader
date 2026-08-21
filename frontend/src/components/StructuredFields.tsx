import type { DetectedField } from "../types";

interface Props {
  fields: DetectedField[];
}

export function StructuredFields({ fields }: Props) {
  if (!fields.length) {
    return (
      <section className="rounded-2xl border border-sand bg-white p-4">
        <h2 className="font-serif text-xl">Detected Information</h2>
        <p className="mt-2 text-slate-600">No fields were confidently detected yet.</p>
      </section>
    );
  }
  return (
    <section className="rounded-2xl border border-sand bg-white p-4">
      <h2 className="font-serif text-xl">Detected Information</h2>
      <dl className="mt-4 grid gap-3">
        {fields.map((field) => (
          <div key={field.field_type} className="rounded-xl bg-paper px-4 py-3">
            <dt className="text-sm uppercase tracking-wide text-slate-500">
              {field.uncertain ? `Possible ${field.label ?? field.field_type}` : field.label ?? field.field_type}
            </dt>
            <dd className="mt-1 text-lg font-semibold">{field.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
