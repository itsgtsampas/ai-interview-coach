import type { ReactNode } from "react";

import type { EvidenceStatus } from "../api/types";
import { useT, type Key } from "../lib/i18n";

/* --- layout: the sheet and its working margin ---------------------------- */

export function Head({ margin, children }: { margin?: ReactNode; children: ReactNode }) {
  return (
    <header className="head">
      <div className="row__margin">{margin}</div>
      <div>{children}</div>
    </header>
  );
}

export function Row({ margin, children }: { margin?: ReactNode; children: ReactNode }) {
  return (
    <div className="row">
      <div className="row__margin">{margin}</div>
      <div>{children}</div>
    </div>
  );
}

/* --- the verdict chip: the only colour in the interface ------------------ */

const VERDICT_KEY: Record<EvidenceStatus, Key> = {
  strong: "verdict.strong",
  partial: "verdict.partial",
  missing: "verdict.missing",
};

export function Verdict({ status }: { status: EvidenceStatus }) {
  const { t } = useT();
  return (
    <span className="verdict" data-v={status}>
      {t(VERDICT_KEY[status])}
    </span>
  );
}

export function Chip({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return (
    <span className="verdict" data-v={tone}>
      {children}
    </span>
  );
}

/* --- signature element: the evidence line --------------------------------
   Every claim the system makes is rendered with the sentence it came from and
   where that sentence lives. If there is no quote, the absence is stated
   rather than hidden — that is the honest case, not a rendering failure.     */

function EvidenceAbsent() {
  const { t } = useT();
  return (
    <p className="evidence evidence--none" style={{ ["--verdict" as string]: "var(--rule)" }}>
      {t("common.noEvidenceLine")}
    </p>
  );
}

export function EvidenceLine({
  quote,
  page,
  section,
  status,
}: {
  quote: string | null;
  page: number | null;
  section: string | null;
  status: EvidenceStatus;
}) {
  if (!quote) {
    return <EvidenceAbsent />;
  }
  const source = ["CV", section || null, page ? `p.${page}` : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <blockquote
      className="evidence"
      style={{ ["--verdict" as string]: `var(--${status})` }}
    >
      “{quote}”
      <cite className="evidence__src label">{source}</cite>
    </blockquote>
  );
}

/* --- data ---------------------------------------------------------------- */

/** 0-100 readiness maps onto the same three-step scale as an evidence verdict,
 *  so a colour always means the same thing wherever it appears. Shared by the
 *  gauges, the charts and the verdict chips. */
export function toneForScore(score: number, max = 100): EvidenceStatus {
  const pct = (score / max) * 100;
  if (pct >= 70) return "strong";
  if (pct >= 45) return "partial";
  return "missing";
}

/* --- feedback ------------------------------------------------------------ */

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="split">
      <span className="spin" aria-hidden="true" />
      {label ? <span className="hint">{label}</span> : null}
    </span>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return (
    <p className="error" role="alert">
      {message}
    </p>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="stack">
      <h2 className="display h3">{title}</h2>
      {children ? <div className="prose">{children}</div> : null}
    </div>
  );
}
