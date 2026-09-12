import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { Answer, Question, SessionOut } from "../api/types";
import {
  Chip, ErrorBox, Head, Row, Spinner, toneForScore,
} from "../components/bits";
import { BulletBar } from "../components/gauges";
import { streamRequest } from "../lib/sse";

interface Ctx { session: SessionOut | null; refresh: () => Promise<void> }

function Feedback({ answer }: { answer: Answer }) {
  const e = answer.evaluation;
  if (!e) return null;
  const scores = Object.fromEntries(e.criteria.map((c) => [c.name, c.score]));
  return (
    <>
      <Row
        margin={
          <>
            <span className="label">Score</span>
            <span className="num" style={{ fontSize: "2rem",
                 color: `var(--${toneForScore(e.overall_score, 5)})` }}>
              {e.overall_score.toFixed(1)}
            </span>
            <span className="label">out of 5</span>
            <Chip tone="neutral">{e.rubric === "star" ? "STAR rubric" : "Technical rubric"}</Chip>
          </>
        }
      >
        {Object.entries(scores)
          .sort((a, b) => a[1] - b[1])
          .map(([name, value], i) => (
            <BulletBar key={name} label={name} value={value} max={5}
                       benchmark={3.5} index={i} />
          ))}
        <details className="disclose">
          <summary>Why this score</summary>
          <p className="reasoning">{e.reasoning}</p>
        </details>
      </Row>

      <Row margin={<span className="label">What worked</span>}>
        <ul className="list list--bullet">
          {e.strengths.map((s) => <li key={s}>{s}</li>)}
        </ul>
      </Row>

      <Row margin={<span className="label">Fix next</span>}>
        <ul className="list list--bullet">
          {e.improvements.map((s) => <li key={s}>{s}</li>)}
        </ul>
      </Row>

      <Row margin={<span className="label">A stronger shape</span>}>
        <p className="prose" style={{ margin: 0, fontSize: "0.89rem" }}>{e.model_answer}</p>
      </Row>

      <Row margin={<span className="label">They would ask</span>}>
        <p className="display h3" style={{ fontWeight: 500 }}>“{e.follow_up_question}”</p>
      </Row>
    </>
  );
}

export function Room() {
  const { session, refresh } = useOutletContext<Ctx>();
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [index, setIndex] = useState(0);
  const [text, setText] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  // Pipeline stages as they are reported, so the wait shows progress.
  const [stages, setStages] = useState<string[]>([]);
  const [seconds, setSeconds] = useState(0);

  const current = questions?.[index];

  useEffect(() => {
    if (!session) return;
    api.listQuestions(session.id).then(setQuestions).catch(setError);
  }, [session?.id]);

  // Load any previous answer when moving between questions.
  useEffect(() => {
    if (!current) return;
    setText("");
    setAnswer(null);
    setSeconds(0);
    if (!current.answered) return;
    api.getAnswer(current.id)
      .then((a) => { setAnswer(a); setText(a.text); })
      .catch((err) => { if (!(err instanceof ApiError && err.status === 404)) setError(err); });
  }, [current?.id]);

  useEffect(() => {
    if (answer || !current) return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [answer, current?.id]);

  const progress = useMemo(
    () => (questions ? questions.filter((q) => q.answered).length : 0),
    [questions],
  );

  async function generate() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      setQuestions(await api.generateQuestions(session.id, 5, 3));
      setIndex(0);
      await refresh();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!current) return;
    setBusy(true);
    setError(null);
    setStages([]);
    try {
      // Scoring takes seconds and produces a structured result, not prose, so
      // there is nothing to type out token by token. What the stream gives is
      // the pipeline reporting itself — which beats a spinner that says nothing.
      const a = await streamRequest<Answer>(
        `/questions/${current.id}/answers/stream`,
        { text: text.trim(), duration_seconds: seconds },
        { onStage: (_key, label) => setStages((all) => [...all, label]) },
      );
      setAnswer(a);
      setQuestions((qs) =>
        qs ? qs.map((q) => (q.id === current.id ? { ...q, answered: true } : q)) : qs);
      await refresh();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
      setStages([]);
    }
  }

  if (!questions) return <div className="sheet"><Spinner label="Loading questions…" /></div>;

  if (questions.length === 0) {
    return (
      <div className="sheet">
        <Head margin={<span className="label">Stage 3</span>}>
          <h1 className="display h1">Practice</h1>
          <p className="prose">
            Eight questions, drawn from your gap analysis. The requirements with no
            evidence come first — those are the ones an interviewer will find.
          </p>
          <ErrorBox error={error} />
          <button className="btn" onClick={generate} disabled={busy}>
            {busy ? "Writing questions…" : "Generate questions"}
          </button>
        </Head>
      </div>
    );
  }

  return (
    <div className="sheet">
      <Head
        margin={
          <>
            <span className="label">Stage 3</span>
            <span className="label">{progress} of {questions.length} answered</span>
          </>
        }
      >
        <h1 className="display h1">Practice</h1>
        <div className="split">
          {questions.map((q, i) => (
            <button
              key={q.id}
              className="btn btn--ghost btn--sm"
              onClick={() => setIndex(i)}
              aria-current={i === index}
              title={q.text}
              style={i === index
                ? { borderColor: "var(--ink)", background: "var(--paper-3)" }
                : q.answered ? { color: "var(--strong)", borderColor: "var(--strong)" } : undefined}
            >
              {i + 1}
            </button>
          ))}
        </div>

        {/* Numbered buttons alone give no sense of what is coming. The list
            shows the whole set so the candidate can choose what to work on
            rather than being marched through it. */}
        <details className="disclose">
          <summary>All {questions.length} questions</summary>
          <ol className="qlist">
            {questions.map((q, i) => (
              <li key={q.id} className="qlist__item" data-current={i === index}>
                <button className="qlist__btn" onClick={() => setIndex(i)}>
                  <span className="qlist__n">{i + 1}</span>
                  <span className="qlist__text">{q.text}</span>
                </button>
                <span className="qlist__tags">
                  <span className="label">{q.category}</span>
                  {q.answered ? (
                    <span className="verdict" data-v="strong">Answered</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ol>
        </details>
      </Head>

      {current ? (
        <>
          <Row
            margin={
              <>
                <Chip tone="neutral">{current.category}</Chip>
                <span className="label">Difficulty {current.difficulty}/5</span>
                {!answer ? (
                  <span className="label">
                    {String(Math.floor(seconds / 60)).padStart(2, "0")}:
                    {String(seconds % 60).padStart(2, "0")}
                  </span>
                ) : null}
              </>
            }
          >
            <h2 className="display h2">{current.text}</h2>
            <p className="hint" style={{ marginTop: "0.7rem" }}>{current.rationale}</p>
          </Row>

          <Row margin={<span className="label">Your answer</span>}>
            <textarea
              className="textarea"
              value={text}
              readOnly={!!answer}
              placeholder="Answer out loud first, then type what you actually said. Aim for 90 seconds of speech."
              onChange={(e) => setText(e.target.value)}
            />
            {/* Each stage the server reports, ticked off as it completes. The
                live region announces only the newest line, so a screen reader
                is not read the whole list again on every update. */}
            {busy || stages.length ? (
              <ol className="stages" aria-label="Scoring progress">
                {stages.map((label, i) => (
                  <li key={`${label}-${i}`} className="stages__s"
                      data-state={i === stages.length - 1 && busy ? "now" : "done"}>
                    <span className="stages__dot" aria-hidden="true" />
                    {label}
                  </li>
                ))}
              </ol>
            ) : null}
            <p className="visually-hidden" role="status" aria-live="polite">
              {busy && stages.length ? stages[stages.length - 1] : ""}
            </p>

            <div className="split" style={{ marginTop: "0.7rem" }}>
              {!answer ? (
                <button className="btn" onClick={submit} disabled={busy || text.trim().length < 10}>
                  {busy ? "Scoring…" : "Submit for scoring"}
                </button>
              ) : (
                <button className="btn btn--ghost" onClick={() => { setAnswer(null); setSeconds(0); }}>
                  Answer again
                </button>
              )}
              {index < questions.length - 1 ? (
                <button className="btn btn--ghost" onClick={() => setIndex(index + 1)}>
                  Next question
                </button>
              ) : (
                <Link className="btn btn--ghost" to={`/session/${session?.id}/scorecard`}>
                  Build scorecard
                </Link>
              )}
            </div>
            <ErrorBox error={error} />
          </Row>

          {answer ? <Feedback answer={answer} /> : null}
        </>
      ) : null}
    </div>
  );
}
