import { useState } from "react";

import { api } from "../api/client";
import type { EvidenceStatus, Suggestion } from "../api/types";
import { ErrorBox, Spinner } from "./bits";
import { useT } from "../lib/i18n";

/** Highlight the [placeholders] so the template reads as a template.
 *
 *  This is the whole point of the feature: the candidate has to see at a glance
 *  which parts are theirs to supply, or they will paste an invented claim into
 *  their CV and get caught in the first ten minutes of a screen. */
function Bullet({ text }: { text: string }) {
  const parts = text.split(/(\[[^\]]+\])/g);
  return (
    <p className="bullet">
      {parts.map((part, i) =>
        part.startsWith("[") && part.endsWith("]") ? (
          <mark key={i} className="slot">{part.slice(1, -1)}</mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </p>
  );
}

export function RewriteCard({
  sessionId, itemId, status, existing,
}: {
  sessionId: number;
  itemId: number;
  status: EvidenceStatus;
  existing?: Suggestion;
}) {
  const { t } = useT();
  const [suggestion, setSuggestion] = useState<Suggestion | null>(existing ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);

  // An evidenced requirement has nothing to rewrite, and the API refuses it.
  if (status === "strong") return null;

  async function ask() {
    setBusy(true);
    setError(null);
    try {
      setSuggestion(await api.suggestRewrite(sessionId, itemId));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!suggestion) return;
    await navigator.clipboard.writeText(suggestion.bullet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (!suggestion) {
    return (
      <div className="rewrite rewrite--ask">
        <button className="btn btn--sm btn--ghost" onClick={ask} disabled={busy}>
          {busy ? <Spinner label={t("common.loading")} /> : t("report.suggestBullet")}
        </button>
        <span className="hint">
          {status === "partial"
            ? "Your CV touches this but does not say it plainly."
            : "See the shape of the bullet that would answer this."}
        </span>
        <ErrorBox error={error} />
      </div>
    );
  }

  return (
    <div className="rewrite">
      <div className="between rewrite__top">
        <span className="label">{t("report.suggestedBullet")}</span>
        <button className="btn btn--link" onClick={copy}>
          {copied ? t("common.copied") : t("common.copy")}
        </button>
      </div>

      <Bullet text={suggestion.bullet} />

      <p className="hint rewrite__slots">
        {t("report.slotsNote")}
      </p>

      {suggestion.premise ? (
        <p className="prose rewrite__p"><strong>{t("report.whyShape")}</strong> {suggestion.premise}</p>
      ) : null}
      {suggestion.why ? <p className="prose rewrite__p">{suggestion.why}</p> : null}
      {suggestion.if_you_cannot ? (
        <p className="prose rewrite__p rewrite__honest">{suggestion.if_you_cannot}</p>
      ) : null}
    </div>
  );
}
