import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import type { SessionOut } from "../api/types";
import { Chip, ErrorBox, Head, Row, Spinner, toneForScore } from "../components/bits";

function statusLabel(s: SessionOut): string {
  if (s.readiness_score != null) return "Scored";
  if (s.answered_count > 0) return `${s.answered_count} answered`;
  if (s.has_analysis) return "Analysed";
  if (s.documents.length === 2) return "Ready";
  return "Needs documents";
}

export function Dashboard() {
  const [sessions, setSessions] = useState<SessionOut[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [title, setTitle] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState<number | null>(null);
  const navigate = useNavigate();

  async function remove(id: number) {
    setError(null);
    try {
      await api.deleteSession(id);
      setSessions((all) => (all ?? []).filter((s) => s.id !== id));
    } catch (err) {
      setError(err);
    } finally {
      setConfirming(null);
    }
  }

  useEffect(() => {
    api.listSessions().then(setSessions).catch(setError);
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await api.createSession(title.trim(), role.trim());
      navigate(`/session/${s.id}/upload`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <div className="sheet">
      <Head margin={<span className="label">Your file</span>}>
        <h1 className="display h1">Sessions</h1>
        <p className="prose" style={{ marginBottom: 0 }}>
          One session pairs a CV with a job description. Everything else — the gap
          analysis, the questions, the scorecard — is derived from that pair.
        </p>
      </Head>

      <Row margin={<span className="label">New</span>}>
        <form onSubmit={create}>
          <div className="field">
            <label className="label" htmlFor="title">Session name</label>
            <input
              id="title" className="input" required minLength={2} value={title}
              placeholder="Meridian Labs — Senior Backend"
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="field">
            <label className="label" htmlFor="role">Target role</label>
            <input
              id="role" className="input" value={role}
              placeholder="Senior Backend Engineer (Python)"
              onChange={(e) => setRole(e.target.value)}
            />
            <span className="hint">Used to shape the behavioural questions.</span>
          </div>
          <ErrorBox error={error} />
          <button className="btn" disabled={busy || title.trim().length < 2}>
            {busy ? "Creating…" : "Create session"}
          </button>
        </form>
      </Row>

      <Row margin={<span className="label">Existing</span>}>
        {sessions === null ? (
          <Spinner label="Loading sessions…" />
        ) : sessions.length === 0 ? (
          <p className="prose">Nothing here yet. Create your first session above.</p>
        ) : (
          <div className="cards">
            {sessions.map((s) => (
              <div key={s.id} className="card">
                <div className="between">
                  <span className="label">{new Date(s.created_at).toLocaleDateString()}</span>
                  <Chip tone={s.readiness_score != null ? toneForScore(s.readiness_score) : "neutral"}>
                    {statusLabel(s)}
                  </Chip>
                </div>
                <Link to={`/session/${s.id}/report`} className="card__body">
                  <h3 className="display h3">{s.title}</h3>
                  {s.target_role ? <p className="hint" style={{ margin: 0 }}>{s.target_role}</p> : null}
                  {s.readiness_score != null ? (
                    <p className="num" style={{ fontSize: "1.6rem", margin: "0.4rem 0 0",
                         color: `var(--${toneForScore(s.readiness_score)})` }}>
                      {s.readiness_score}
                      <span className="gauge__d"> /100 ready</span>
                    </p>
                  ) : null}
                </Link>

                {/* Deleting removes the uploaded CV, its vectors and every
                    derived result. A CV is personal data, so this has to be
                    reachable — and has to confirm first. */}
                {confirming === s.id ? (
                  <div className="split card__confirm">
                    <span className="hint">Delete this session and its documents?</span>
                    <button className="btn btn--sm" onClick={() => remove(s.id)}>Delete</button>
                    <button className="btn btn--ghost btn--sm"
                            onClick={() => setConfirming(null)}>Keep</button>
                  </div>
                ) : (
                  <button className="btn btn--link card__delete"
                          onClick={() => setConfirming(s.id)}>
                    Delete
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </Row>
    </div>
  );
}
