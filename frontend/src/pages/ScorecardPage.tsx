import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { Scorecard, SessionOut } from "../api/types";
import { Bars, Chip, ErrorBox, Head, Row, Spinner } from "../components/bits";
import { Ring } from "../components/charts";
import { DownloadPdf } from "../components/DownloadPdf";

interface Ctx { session: SessionOut | null; refresh: () => Promise<void> }

const PRIORITY_TONE = { high: "missing", medium: "partial", low: "neutral" } as const;

export function ScorecardPage() {
  const { session, refresh } = useOutletContext<Ctx>();
  const [card, setCard] = useState<Scorecard | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!session) return;
    api.getScorecard(session.id)
      .then(setCard)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) setMissing(true);
        else setError(err);
      });
  }, [session?.id]);

  async function build() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      setCard(await api.buildScorecard(session.id));
      setMissing(false);
      await refresh();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (missing) {
    return (
      <div className="sheet">
        <Head margin={<span className="label">Stage 4</span>}>
          <h1 className="display h1">Scorecard</h1>
          <p className="prose">
            The scorecard combines your CV match with how you actually answered. Answer at
            least one question first.
          </p>
          <ErrorBox error={error} />
          <div className="split">
            <button className="btn" onClick={build} disabled={busy}>
              {busy ? "Building…" : "Build scorecard"}
            </button>
            <Link className="btn btn--ghost" to={`/session/${session?.id}/room`}>
              Back to practice
            </Link>
          </div>
        </Head>
      </div>
    );
  }

  if (!card) return <div className="sheet"><Spinner label="Loading scorecard…" /></div>;

  return (
    <div className="sheet">
      <Head margin={<span className="label">Stage 4</span>}>
        <h1 className="display h1">Scorecard</h1>
        <div className="scorehead">
          <Ring value={card.readiness_score} label={card.readiness_band} />
          <div>
            <p className="prose scorehead__sum">{card.summary}</p>
            <DownloadPdf sessionId={card.session_id} />
          </div>
        </div>
        <ErrorBox error={error} />
      </Head>

      {Object.keys(card.competencies).length ? (
        <Row margin={<span className="label">Competencies</span>}>
          <Bars data={card.competencies} max={5} />
          <p className="hint" style={{ marginTop: "0.8rem" }}>
            Averaged across every answer you scored, weakest first.
          </p>
        </Row>
      ) : null}

      {card.strengths.length ? (
        <Row margin={<span className="label">Strengths</span>}>
          <ul className="list list--bullet">
            {card.strengths.map((s) => <li key={s}>{s}</li>)}
          </ul>
        </Row>
      ) : null}

      {card.gaps.length ? (
        <Row margin={<span className="label">Gaps</span>}>
          <ul className="list list--bullet">
            {card.gaps.map((s) => <li key={s}>{s}</li>)}
          </ul>
        </Row>
      ) : null}

      <Row margin={<span className="label">Do this next</span>}>
        {card.action_items.map((a) => (
          <div className="action" key={a.title}>
            <div>
              <Chip tone={PRIORITY_TONE[a.priority]}>{a.priority}</Chip>
            </div>
            <div>
              <h3 className="display h3">{a.title}</h3>
              {a.why ? <p className="prose" style={{ margin: "0.3rem 0 0", fontSize: "0.87rem" }}>{a.why}</p> : null}
              {a.how ? (
                <p className="hint" style={{ margin: "0.35rem 0 0" }}>
                  <strong>How:</strong> {a.how}
                </p>
              ) : null}
            </div>
          </div>
        ))}
        <div className="split mt">
          <button className="btn btn--ghost" onClick={build} disabled={busy}>
            {busy ? "Rebuilding…" : "Rebuild from latest answers"}
          </button>
          <Link className="btn btn--ghost" to={`/session/${session?.id}/letter`}>
            Write a cover letter
          </Link>
          <Link className="btn btn--ghost" to={`/session/${session?.id}/coach`}>
            Ask the coach
          </Link>
        </div>
      </Row>
    </div>
  );
}
