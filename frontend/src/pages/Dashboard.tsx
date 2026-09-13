import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import type { SessionOut } from "../api/types";
import { Chip, ErrorBox, Head, Row, Spinner, toneForScore } from "../components/bits";
import { useT } from "../lib/i18n";

function useStatusLabel() {
  const { t } = useT();
  return (s: SessionOut): string => {
    if (s.readiness_score != null) return t("dash.scored");
    if (s.answered_count > 0) return t("dash.answered", { n: s.answered_count });
    if (s.has_analysis) return t("dash.analysed");
    if (s.documents.length === 2) return t("dash.ready");
    return t("dash.needsDocs");
  };
}

export function Dashboard() {
  const { t } = useT();
  const statusLabel = useStatusLabel();
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
      <Head margin={<span className="label">{t("nav.sessions")}</span>}>
        <h1 className="display h1">{t("dash.title")}</h1>
        <p className="prose" style={{ marginBottom: 0 }}>
          {t("dash.lead")}
        </p>
      </Head>

      <Row margin={<span className="label">{t("dash.new")}</span>}>
        <form onSubmit={create}>
          <div className="field">
            <label className="label" htmlFor="title">{t("dash.name")}</label>
            <input
              id="title" className="input" required minLength={2} value={title}
              placeholder="Meridian Labs — Senior Backend"
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="field">
            <label className="label" htmlFor="role">{t("dash.role")}</label>
            <input
              id="role" className="input" value={role}
              placeholder="Senior Backend Engineer (Python)"
              onChange={(e) => setRole(e.target.value)}
            />
            <span className="hint">{t("dash.roleHint")}</span>
          </div>
          <ErrorBox error={error} />
          <button className="btn" disabled={busy || title.trim().length < 2}>
            {busy ? t("dash.creating") : t("dash.create")}
          </button>
        </form>
      </Row>

      <Row margin={<span className="label">{t("dash.existing")}</span>}>
        {sessions === null ? (
          <Spinner label={t("common.loading")} />
        ) : sessions.length === 0 ? (
          <p className="prose">{t("dash.empty")}</p>
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
                      <span className="gauge__d"> {t("score.readySuffix")}</span>
                    </p>
                  ) : null}
                </Link>

                {/* Deleting removes the uploaded CV, its vectors and every
                    derived result. A CV is personal data, so this has to be
                    reachable — and has to confirm first. */}
                {confirming === s.id ? (
                  <div className="split card__confirm">
                    <span className="hint">{t("dash.confirmDelete")}</span>
                    <button className="btn btn--sm" onClick={() => remove(s.id)}>{t("common.delete")}</button>
                    <button className="btn btn--ghost btn--sm"
                            onClick={() => setConfirming(null)}>{t("common.keep")}</button>
                  </div>
                ) : (
                  <button className="btn btn--link card__delete"
                          onClick={() => setConfirming(s.id)}>
                    {t("common.delete")}
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
