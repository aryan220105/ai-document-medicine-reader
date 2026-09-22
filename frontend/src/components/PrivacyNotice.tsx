interface Props {
  notice: string;
  allowAi: boolean;
  aiEnabled: boolean;
  onAllowAi: (value: boolean) => void;
}

export function PrivacyNotice({ notice, allowAi, aiEnabled, onAllowAi }: Props) {
  return (
    <section className="rounded-md border border-slate-300 bg-white p-4 text-sm text-slate-700" data-testid="privacy-notice">
      <h2 className="font-semibold text-slate-900">Privacy and academic use</h2>
      <p className="mt-2">{notice}</p>
      <p className="mt-2">
        FormSathi does not submit forms to any government, bank, insurer, or school. The completed file is a
        reference preview for you to copy by hand.
      </p>
      <label className="mt-3 flex items-start gap-2">
        <input
          type="checkbox"
          checked={allowAi}
          disabled={!aiEnabled}
          onChange={(event) => onAllowAi(event.target.checked)}
        />
        <span>
          Allow external AI for unknown fields only. Printed labels are sent, never your answers or the page image.
          {!aiEnabled ? " External AI is not configured on this server." : ""}
        </span>
      </label>
    </section>
  );
}
