import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { Progress as ProgressData } from "../api/types";
import { DataTable, Delta, Sparkline, Stat, Trend } from "../components/charts";
import { ArcGauge } from "../components/gauges";
import { Empty, ErrorBox, Head, Row, Spinner, toneForScore } from "../components/bits";

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function Progress() {
  const [data, setData] = useState<ProgressData | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.progress().then(setData).catch(setError);
  }, []);

  if (error) return <div className="sheet"><ErrorBox error={error} /></div>;
  if (!data) return <div className="sheet"><Spinner label="Reading your sessions…" /></div>;

  if (data.sessions_total === 0) {
    return (
      <div className="sheet">
        <Head margin={<span className="label">Across sessions</span>}>
          <Empty title="Nothing to compare yet">
            <p>
              This page comes alive once you have run more than one application. It
              is where the same gap showing up in three postings becomes visible —
              which is the thing worth going away and learning.
            </p>
            <Link className="btn" to="/">Start a session</Link>
          </Empty>
        </Head>
      </div>
    );
  }

  const scored = data.points.filter((p) => p.readiness_score !== null);
  const trendPoints = scored.map((p) => ({
    label: p.title,
    value: p.readiness_score as number,
    meta: `${shortDate(p.created_at)} · ${p.answers} answered`,
  }));

  return (
    <div className="sheet">
      <Head margin={<span className="label">Across sessions</span>}>
        <h1 className="display h1">Progress</h1>
        <p className="prose" style={{ marginBottom: 0 }}>
          Every other page judges one application. This one looks at all
          {" "}{data.sessions_total} of them together, which is the only place a
          pattern can show up.
        </p>
      </Head>

      {/* --- the headline figures ------------------------------------------ */}
      <Row margin={<span className="label">Where you are</span>}>
        <div className="statrow">
          {data.latest_readiness !== null ? (
            <ArcGauge value={data.latest_readiness} band="Latest readiness" />
          ) : null}
          <div className="stats">
            <Stat
              label="Sessions"
              value={data.sessions_total}
              note={`${data.sessions_scored} scored`}
            />
            {data.mean_match !== null ? (
              <Stat
                label="Average CV match"
                value={data.mean_match}
                suffix="/100"
                tone={toneForScore(data.mean_match)}
              />
            ) : null}
            <Stat label="Answers practised" value={data.answers_total} />
            {data.mean_answer_score !== null ? (
              <Stat
                label="Average answer"
                value={data.mean_answer_score.toFixed(1)}
                suffix="/5"
                tone={toneForScore(data.mean_answer_score, 5)}
              />
            ) : null}
          </div>
        </div>

        {data.readiness_delta !== null ? (
          <p className="prose deltaline">
            Since your first scored session:{" "}
            <Delta value={data.readiness_delta} suffix=" points" />
            {data.best_readiness !== null && data.best_readiness !== data.latest_readiness ? (
              <span className="hint"> · best so far {data.best_readiness}/100</span>
            ) : null}
          </p>
        ) : null}
      </Row>

      {/* --- the trend, or an honest refusal to draw one -------------------- */}
      <Row margin={<span className="label">Readiness</span>}>
        {data.has_trend ? (
          <>
            <Trend
              points={trendPoints}
              caption="Numbered in the order you ran them. Hover or tab through a point for its session."
            />
            <DataTable
              caption="Readiness score per session, oldest first."
              columns={["Session", "Date", "CV match", "Readiness", "Answers"]}
              rows={scored.map((p) => [
                p.title,
                shortDate(p.created_at),
                p.match_score ?? "—",
                p.readiness_score ?? "—",
                p.answers,
              ])}
            />
          </>
        ) : (
          <>
            <p className="prose">
              {scored.length === 0
                ? "No session has been scored yet. Finish a scorecard and it will appear here."
                : `A line through ${scored.length} point${scored.length === 1 ? "" : "s"} would ` +
                  "suggest a direction the data cannot support. Here are the scores instead; " +
                  "the chart appears at three."}
            </p>
            {scored.length > 0 ? (
              <div className="pointlist">
                {scored.map((p) => (
                  <Link key={p.session_id} to={`/session/${p.session_id}/scorecard`}
                        className="pointlist__row">
                    <span className="pointlist__t">{p.title}</span>
                    <span className="hint">{shortDate(p.created_at)}</span>
                    <span className="num" style={{
                      color: `var(--${toneForScore(p.readiness_score as number)})` }}>
                      {p.readiness_score}
                      <span className="gauge__d">/100</span>
                    </span>
                  </Link>
                ))}
              </div>
            ) : null}
          </>
        )}
      </Row>

      {/* --- the actual insight -------------------------------------------- */}
      {data.recurring_gaps.length ? (
        <Row margin={<span className="label">Keeps costing you</span>}>
          <p className="prose">
            These went unevidenced in more than one application. A gap in one posting
            is a mismatch; the same gap in several is the thing to go and learn.
          </p>
          <ul className="gaps">
            {data.recurring_gaps.map((gap) => (
              <li key={gap.requirement} className="gap">
                <span className="gap__count num" aria-hidden="true">{gap.missing_in}</span>
                <div>
                  <p className="gap__req">{gap.requirement}</p>
                  <p className="hint gap__where">
                    Missing in {gap.missing_in} of {data.sessions_total}:{" "}
                    {gap.sessions.join(", ")}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </Row>
      ) : null}

      {/* --- competency movement -------------------------------------------- */}
      {data.competencies.length ? (
        <Row margin={<span className="label">Competencies</span>}>
          <p className="prose">
            Averaged per session, weakest movement first. Each is scored out of five.
          </p>
          <table className="table table--trend">
            <thead>
              <tr>
                <th scope="col">Competency</th>
                <th scope="col">Trend</th>
                <th scope="col">First</th>
                <th scope="col">Latest</th>
                <th scope="col">Change</th>
              </tr>
            </thead>
            <tbody>
              {data.competencies.map((c) => (
                <tr key={c.name}>
                  <th scope="row">{c.name}</th>
                  <td><Sparkline values={c.points} /></td>
                  <td className="num">{c.first.toFixed(1)}</td>
                  <td className="num" style={{ color: `var(--${toneForScore(c.latest, 5)})` }}>
                    {c.latest.toFixed(1)}
                  </td>
                  <td><Delta value={Number(c.delta.toFixed(1))} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Row>
      ) : null}

      <Row margin={<span className="label">All sessions</span>}>
        <div className="pointlist">
          {[...data.points].reverse().map((p) => (
            <Link key={p.session_id} to={`/session/${p.session_id}/report`}
                  className="pointlist__row">
              <span className="pointlist__t">{p.title}</span>
              <span className="hint">{shortDate(p.created_at)}</span>
              <span className="hint">
                {p.match_score !== null ? `match ${p.match_score}` : "not analysed"}
              </span>
              {p.readiness_score !== null ? (
                <span className="num" style={{
                  color: `var(--${toneForScore(p.readiness_score)})` }}>
                  {p.readiness_score}<span className="gauge__d">/100</span>
                </span>
              ) : <span className="hint">—</span>}
            </Link>
          ))}
        </div>
      </Row>
    </div>
  );
}
