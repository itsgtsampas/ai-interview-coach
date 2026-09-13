import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { MatchReport, SessionOut, Suggestion } from "../api/types";
import {
  Chip, ErrorBox, EvidenceLine, Head, Row, Spinner, Verdict,
} from "../components/bits";
import { ArcGauge } from "../components/gauges";
import { useT } from "../lib/i18n";
import { RewriteCard } from "../components/RewriteCard";

interface Ctx { session: SessionOut | null; refresh: () => Promise<void> }

export function Report() {
  const { session, refresh } = useOutletContext<Ctx>();
  const { t } = useT();
  const [report, setReport] = useState<MatchReport | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [missing, setMissing] = useState(false);
  // Suggestions already written for this session, so revisiting the page does
  // not hide work the user has paid for.
  const [rewrites, setRewrites] = useState<Record<number, Suggestion>>({});

  useEffect(() => {
    if (!session) return;
    api.getAnalysis(session.id)
      .then(setReport)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) setMissing(true);
        else setError(err);
      });
    api.listRewrites(session.id)
      .then((all) => setRewrites(Object.fromEntries(all.map((r) => [r.match_item_id, r]))))
      .catch(() => setRewrites({}));
  }, [session?.id]);

  async function run() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      setReport(await api.runAnalysis(session.id));
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
        <Head margin={<span className="label">{t("stage.label")} 2</span>}>
          <h1 className="display h1">{t("report.title")}</h1>
          <p className="prose">{t("report.none")}</p>
          <ErrorBox error={error} />
          <div className="split">
            <button className="btn" onClick={run} disabled={busy}>
              {busy ? t("report.running") : t("report.run")}
            </button>
            <Link className="btn btn--ghost" to={`/session/${session?.id}/upload`}>
              Check documents
            </Link>
          </div>
        </Head>
      </div>
    );
  }

  if (!report) {
    return <div className="sheet"><Spinner label={t("common.loading")} /></div>;
  }

  const counts = report.counts ?? {};
  const behavioural = report.items.filter((i) => i.kind === "behavioural");

  return (
    <div className="sheet">
      <Head margin={<span className="label">{t("stage.label")} 2</span>}>
        <h1 className="display h1">{t("report.title")}</h1>
        <div className="scorehead">
          <ArcGauge value={report.overall_score} band={report.verdict}
                    caption={t("report.ofRole")} />
          <div>
            <p className="prose scorehead__sum">{report.summary}</p>
          </div>
        </div>
        <div className="split" style={{ marginTop: "0.9rem" }}>
          <Chip tone="strong">{t("count.evidenced", { n: counts.strong ?? 0 })}</Chip>
          <Chip tone="partial">{t("count.thin", { n: counts.partial ?? 0 })}</Chip>
          <Chip tone="missing">{t("count.missing", { n: counts.missing ?? 0 })}</Chip>
        </div>
        <ErrorBox error={error} />
      </Head>

      {report.items.filter((i) => i.kind !== "behavioural").map((item) => (
        <Row
          key={item.id}
          margin={
            <>
              <Verdict status={item.status} />
              <span className="label">
                {item.category === "must_have" ? t("verdict.mustHave") : t("verdict.niceToHave")}
              </span>
            </>
          }
        >
          <h2 className="display h3">{item.requirement}</h2>
          <p className="prose" style={{ margin: "0.4rem 0 0", fontSize: "0.89rem" }}>
            {item.reasoning}
          </p>
          <EvidenceLine
            quote={item.evidence_quote}
            page={item.evidence_page}
            section={item.evidence_section}
            status={item.status}
          />
          <RewriteCard
            sessionId={session?.id ?? 0}
            itemId={item.id}
            status={item.status}
            existing={rewrites[item.id]}
          />
        </Row>
      ))}

      {/* Requirements no CV can evidence. Scoring them would mark the candidate
          down for a limitation of the medium, so they are shown apart and
          carry no verdict — they become interview questions instead. */}
      {behavioural.length ? (
        <Row margin={<span className="label">{t("report.notOnCv")}</span>}>
          <h2 className="display h3">{t("report.askedInInterview")}</h2>
          <p className="prose" style={{ margin: "0.4rem 0 0.9rem", fontSize: "0.89rem" }}>
            The posting asks for {behavioural.length === 1 ? "this" : "these"} too. No CV
            can show {behavioural.length === 1 ? "it" : "them"}, so {behavioural.length === 1
            ? "it is" : "they are"} left out of the score and turned into practice questions.
          </p>
          <ul className="list list--bullet">
            {behavioural.map((i) => <li key={i.id}>{i.requirement}</li>)}
          </ul>
        </Row>
      ) : null}

      <Row margin={<span className="label">{t("common.next")}</span>}>
        <p className="prose">
          The questions are built from this table: the requirements with no evidence come
          first, because those are the ones that end interviews.
        </p>
        <Link className="btn" to={`/session/${session?.id}/room`}>
          {t("report.goToPractice")}
        </Link>
        <p className="hint" style={{ marginTop: "0.8rem" }}>
          Generated by prompt <code>{report.prompt_version}</code>.
        </p>
      </Row>
    </div>
  );
}
