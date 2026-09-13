import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { SessionOut } from "../api/types";
import { StepProgress } from "./gauges";
import { useT, type Key } from "../lib/i18n";

type T = ReturnType<typeof useT>["t"];
/** The five stages are a real sequence — documents feed the analysis, the
 *  analysis feeds the questions, the answers feed the scorecard — so numbering
 *  them encodes the dependency rather than decorating the list. */
const STAGES = [
  { n: 1, to: "upload", label: "stage.documents" },
  { n: 2, to: "report", label: "stage.report" },
  { n: 3, to: "room", label: "stage.room" },
  { n: 4, to: "scorecard", label: "stage.scorecard" },
  { n: 5, to: "letter", label: "stage.letter" },
  { n: 6, to: "coach", label: "stage.coach" },
] as const satisfies readonly { n: number; to: string; label: Key }[];

type Stage = (typeof STAGES)[number];

function bothDocumentsReady(s: SessionOut): boolean {
  const ready = s.documents.filter((d) => d.ingest_status === "ready");
  return new Set(ready.map((d) => d.kind)).size === 2;
}

function isDone(stage: Stage, s: SessionOut | null): boolean {
  if (!s) return false;
  if (stage.to === "upload") return bothDocumentsReady(s);
  if (stage.to === "report") return s.has_analysis;
  if (stage.to === "room") return s.question_count > 0 && s.answered_count === s.question_count;
  if (stage.to === "scorecard") return s.readiness_score != null;
  return false;  // the letter and the coach are revisitable, never "done"
}

/** Why a stage cannot be opened yet — shown to the user rather than left as a
 *  dead link with no explanation. */
function blockedBecause(stage: Stage, s: SessionOut | null, t: T): string | null {
  if (!s) return null;
  if (stage.to === "upload") return null;
  if (!bothDocumentsReady(s)) return t("rail.needDocs");
  if (stage.to === "report") return null;
  if (!s.has_analysis) return t("rail.needAnalysis");
  if (stage.to === "scorecard" && s.answered_count === 0) return t("rail.needAnswer");
  // The letter is written from the gap analysis alone, so it unlocks with it —
  // it does not need a scorecard the way the rail's order might suggest.
  return null;
}

/** A short progress note, so the rail carries state and not just labels. */
function progress(stage: Stage, s: SessionOut | null, t: T): string | null {
  if (!s) return null;
  if (stage.to === "upload") {
    const ready = s.documents.filter((d) => d.ingest_status === "ready").length;
    return ready === 2 ? t("rail.bothDocs") : t("rail.docsOf", { n: ready });
  }
  if (stage.to === "room" && s.question_count > 0) {
    return t("rail.answeredOf", { done: s.answered_count, total: s.question_count });
  }
  if (stage.to === "scorecard" && s.readiness_score != null) {
    return t("rail.ready", { n: s.readiness_score });
  }
  return null;
}

function SessionSwitcher({ currentId }: { currentId: number }) {
  const { t } = useT();
  const [sessions, setSessions] = useState<SessionOut[] | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (open && sessions === null) api.listSessions().then(setSessions).catch(() => setSessions([]));
  }, [open, sessions]);

  const others = (sessions ?? []).filter((s) => s.id !== currentId);

  return (
    <details className="disclose switcher" open={open}
             onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>{t("stage.switch")}</summary>
      {sessions === null ? (
        <p className="hint switcher__empty">{t("common.loading")}</p>
      ) : others.length === 0 ? (
        <p className="hint switcher__empty">{t("stage.onlySession")}</p>
      ) : (
        <ul className="switcher__list">
          {others.map((s) => (
            <li key={s.id}>
              <Link to={`/session/${s.id}/report`} className="switcher__link">
                {s.title}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Link to="/" className="switcher__new">{t("stage.newSession")}</Link>
    </details>
  );
}

export function Rail({ session }: { session: SessionOut | null }) {
  const { t } = useT();
  const { id } = useParams();
  // useLocation rather than window.location: the rail must re-render when the
  // route changes, and reading the global would not subscribe it to that.
  const active = useLocation().pathname.split("/").pop() ?? "";

  return (
    <nav className="rail" aria-label="Main">
      {id ? (
        <div className="rail__ctx">
          <Link to="/" className="rail__back label">← {t("stage.allSessions")}</Link>
          <h2 className="rail__title">{session?.title ?? "…"}</h2>
          {session?.target_role ? (
            <p className="rail__role">{session.target_role}</p>
          ) : null}
          <StepProgress
            done={STAGES.filter((st) => isDone(st, session)).length}
            total={STAGES.length}
            label={t("stage.ofStages", {
              done: STAGES.filter((st) => isDone(st, session)).length,
              total: STAGES.length,
            })}
          />
          <SessionSwitcher currentId={Number(id)} />
        </div>
      ) : null}

      {id ? (
        <ol className="stepper">
          {STAGES.map((stage) => {
            const blocked = blockedBecause(stage, session, t);
            const note = progress(stage, session, t);
            const state = active === stage.to ? "active" : isDone(stage, session) ? "done" : "todo";
            return (
              <li key={stage.to} className="step" data-state={state} aria-disabled={!!blocked}>
                <span className="step__n" aria-hidden="true">{stage.n}</span>
                <NavLink
                  to={`/session/${id}/${stage.to}`}
                  className="step__link"
                  title={blocked ?? undefined}
                  aria-current={active === stage.to ? "page" : undefined}
                >
                  {t(stage.label)}
                </NavLink>
                {note && !blocked ? <span className="step__meta">{note}</span> : null}
                {blocked && active !== stage.to ? (
                  <span className="step__meta step__meta--blocked">{blocked}</span>
                ) : null}
              </li>
            );
          })}
        </ol>
      ) : null}

    </nav>
  );
}
