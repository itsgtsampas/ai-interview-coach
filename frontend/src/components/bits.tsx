import type { ReactNode } from "react";

import type { EvidenceStatus } from "../api/types";

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

const VERDICT_COPY: Record<EvidenceStatus, string> = {
  strong: "Evidenced",
  partial: "Thin",
  missing: "No evidence",
};

export function Verdict({ status }: { status: EvidenceStatus }) {
  return (
    <span className="verdict" data-v={status}>
      {VERDICT_COPY[status]}
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
    return (
      <p className="evidence evidence--none" style={{ ["--verdict" as string]: "var(--rule)" }}>
        No sentence in the CV supports this.
      </p>
    );
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

export function Meter({ value, max = 100, tone }: { value: number; max?: number; tone?: string }) {
  return (
    <div className="meter">
      <div
        className="meter__fill"
        style={{
          width: `${Math.min(100, (value / max) * 100)}%`,
          ["--verdict" as string]: tone ? `var(--${tone})` : "var(--ink)",
        }}
      />
    </div>
  );
}

/** 0-100 readiness maps onto the same three-step scale as an evidence verdict,
 *  so a colour always means the same thing wherever it appears. */
export function toneForScore(score: number, max = 100): EvidenceStatus {
  const pct = (score / max) * 100;
  if (pct >= 70) return "strong";
  if (pct >= 45) return "partial";
  return "missing";
}

export function Gauge({ value, suffix = "/100" }: { value: number; suffix?: string }) {
  return (
    <div className="gauge">
      <span className="num gauge__n" style={{ color: `var(--${toneForScore(value)})` }}>
        {value}
      </span>
      <span className="gauge__d">{suffix}</span>
    </div>
  );
}

export function Bars({ data, max = 5 }: { data: Record<string, number>; max?: number }) {
  const entries = Object.entries(data).sort((a, b) => a[1] - b[1]);
  if (!entries.length) return null;
  return (
    <div className="bars">
      {entries.map(([name, value]) => (
        <div key={name}>
          <div className="bar__top">
            <span className="bar__name">{name}</span>
            <span className="bar__val">
              {value.toFixed(1)} / {max}
            </span>
          </div>
          <Meter value={value} max={max} tone={toneForScore(value, max)} />
        </div>
      ))}
    </div>
  );
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
