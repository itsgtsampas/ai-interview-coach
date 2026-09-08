import { Link, NavLink, useParams } from "react-router-dom";

import { useAuth } from "../lib/auth";
import type { SessionOut } from "../api/types";

/** The four stages are a real sequence — analysis feeds questions, questions
 *  feed answers, answers feed the scorecard — so numbering them encodes the
 *  dependency rather than decorating the list. */
const STAGES = [
  { n: 1, to: "report", label: "Gap analysis" },
  { n: 2, to: "room", label: "Practice" },
  { n: 3, to: "scorecard", label: "Scorecard" },
  { n: 4, to: "coach", label: "Coach" },
] as const;

function stageState(stage: (typeof STAGES)[number], session: SessionOut | null, active: string) {
  if (active === stage.to) return "active";
  if (!session) return "todo";
  if (stage.to === "report") return session.has_analysis ? "done" : "todo";
  if (stage.to === "room") return session.answered_count > 0 ? "done" : "todo";
  if (stage.to === "scorecard") return session.readiness_score != null ? "done" : "todo";
  return "todo";
}

function stageEnabled(stage: (typeof STAGES)[number], session: SessionOut | null) {
  if (!session) return false;
  if (stage.to === "report") return true;
  if (stage.to === "room") return session.has_analysis;
  if (stage.to === "scorecard") return session.answered_count > 0;
  return session.has_analysis;
}

export function Rail({ session }: { session: SessionOut | null }) {
  const { signOut, user } = useAuth();
  const params = useParams();
  const active = window.location.pathname.split("/").pop() ?? "";

  return (
    <nav className="rail" aria-label="Main">
      <Link to="/" className="brand">
        <div className="brand__mark">
          Interview
          <br />
          Coach
        </div>
        <div className="brand__sub label">Evidence-first prep</div>
      </Link>

      {params.id ? (
        <ol className="stepper">
          {STAGES.map((stage) => {
            const enabled = stageEnabled(stage, session);
            return (
              <li
                key={stage.to}
                className="step"
                data-state={stageState(stage, session, active)}
                aria-disabled={!enabled}
              >
                <span className="step__n" aria-hidden="true">
                  {stage.n}
                </span>
                <NavLink to={`/session/${params.id}/${stage.to}`} className="step__link">
                  {stage.label}
                </NavLink>
              </li>
            );
          })}
        </ol>
      ) : null}

      <div className="rail__foot">
        <Link to="/" className="label" style={{ textDecoration: "none" }}>
          All sessions
        </Link>
        {user ? <span className="label">{user.email}</span> : null}
        <button className="btn btn--link" onClick={signOut}>
          Sign out
        </button>
      </div>
    </nav>
  );
}
