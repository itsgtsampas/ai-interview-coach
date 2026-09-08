import { useState } from "react";
import { useOutletContext } from "react-router-dom";

import { api } from "../api/client";
import type { CoachStep, SessionOut } from "../api/types";
import { ErrorBox, Head, Row, Spinner } from "../components/bits";

interface Ctx { session: SessionOut | null }

interface Turn {
  question: string;
  answer: string;
  steps: CoachStep[];
}

const SUGGESTIONS = [
  "What are my biggest gaps for this role?",
  "Does my CV show anything about Kubernetes?",
  "How am I doing on my practice answers so far?",
  "What does this job actually require?",
];

export function Coach() {
  const { session } = useOutletContext<Ctx>();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function ask(text: string) {
    if (!session || text.trim().length < 3) return;
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      const res = await api.askCoach(session.id, text.trim());
      setTurns((t) => [...t, { question: text.trim(), answer: res.answer, steps: res.steps }]);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="sheet">
      <Head margin={<span className="label">Stage 4</span>}>
        <h1 className="display h1">Coach</h1>
        <p className="prose" style={{ marginBottom: 0 }}>
          The coach can read your CV, the job description, your gap analysis and your
          scores. It decides which of those to consult for each question, and shows you
          every lookup it made — so you can check the answer rather than trust it.
        </p>
      </Head>

      <Row margin={<span className="label">Conversation</span>}>
        {turns.length === 0 ? (
          <div className="stack">
            <p className="hint">Try one of these:</p>
            <div className="split">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="btn btn--ghost btn--sm" onClick={() => ask(s)} disabled={busy}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat">
            {turns.map((t, i) => (
              <div key={i} className="stack">
                <p className="msg--you" style={{ margin: 0 }}>{t.question}</p>
                <p className="msg--coach" style={{ margin: 0 }}>{t.answer}</p>
                {t.steps.length ? (
                  <details className="disclose">
                    <summary>
                      Reasoning — {t.steps.filter((s) => s.tool).length} lookup
                      {t.steps.filter((s) => s.tool).length === 1 ? "" : "s"}
                    </summary>
                    <div className="trace">
                      {t.steps.map((s, j) => (
                        <div key={j} className="trace__step">
                          <span className="label">
                            {s.tool ? `Step ${j + 1} · ${s.tool}` : `Step ${j + 1} · answer`}
                          </span>
                          <div>{s.thought}</div>
                          {s.observation ? <div className="trace__obs">{s.observation}</div> : null}
                        </div>
                      ))}
                    </div>
                  </details>
                ) : null}
              </div>
            ))}
          </div>
        )}

        {busy ? <Spinner label="Looking things up…" /> : null}
        <ErrorBox error={error} />

        <form
          className="split mt"
          onSubmit={(e) => { e.preventDefault(); ask(message); }}
          style={{ flexWrap: "nowrap" }}
        >
          <input
            className="input"
            value={message}
            placeholder="Ask about your CV, the role, or your scores"
            onChange={(e) => setMessage(e.target.value)}
          />
          <button className="btn" disabled={busy || message.trim().length < 3}>Ask</button>
        </form>
      </Row>
    </div>
  );
}
