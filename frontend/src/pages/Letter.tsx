import { useEffect, useRef, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { CoverLetter, LetterTone, SessionOut } from "../api/types";
import { ErrorBox, Head, Row, Spinner } from "../components/bits";
import { streamRequest } from "../lib/sse";
import { useT } from "../lib/i18n";

interface Ctx { session: SessionOut | null; refresh: () => Promise<void> }

const TONES: { value: LetterTone; label: string; note: string }[] = [
  { value: "plain", label: "Plain", note: "Short sentences, no adjectives about yourself." },
  { value: "warm", label: "Warm", note: "Human and specific, still concise." },
  { value: "formal", label: "Formal", note: "Conventional register — banks, public sector." },
];

export function Letter() {
  const { session } = useOutletContext<Ctx>();
  const { t } = useT();
  const [letter, setLetter] = useState<CoverLetter | null>(null);
  const [tone, setTone] = useState<LetterTone>("plain");
  const [streamed, setStreamed] = useState("");
  const [stage, setStage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!session) return;
    api.getCoverLetter(session.id)
      .then((l) => { setLetter(l); setTone(l.tone); })
      .catch((err) => {
        if (!(err instanceof ApiError && err.status === 404)) setError(err);
      });
  }, [session?.id]);

  // An in-flight stream must not outlive the page that started it.
  useEffect(() => () => abort.current?.abort(), []);

  async function write() {
    if (!session) return;
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;

    setBusy(true);
    setError(null);
    setStreamed("");
    setLetter(null);
    setStage(null);

    try {
      const done = await streamRequest<CoverLetter>(
        `/sessions/${session.id}/cover-letter/stream`,
        { tone },
        {
          onStage: (_key, label) => setStage(label),
          onToken: (text) => { setStage(null); setStreamed((s) => s + text); },
        },
        controller.signal,
      );
      setLetter(done);
      setStreamed("");
    } catch (err) {
      if (!controller.signal.aborted) setError(err);
    } finally {
      setBusy(false);
      setStage(null);
    }
  }

  async function copy() {
    const text = letter?.body ?? streamed;
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const showing = letter?.body ?? streamed;

  return (
    <div className="sheet">
      <Head margin={<span className="label">{t("stage.label")} 5</span>}>
        <h1 className="display h1">{t("letter.title")}</h1>
        <p className="prose" style={{ marginBottom: 0 }}>
          Written from the requirements your CV actually evidenced, and from the
          sentences that evidenced them. Anything the gap analysis could not find
          is never passed to the model, so it cannot appear here as a strength.
        </p>
      </Head>

      <Row margin={<span className="label">{t("letter.tone")}</span>}>
        <div className="tones" role="radiogroup" aria-label={t("letter.tone")}>
          {TONES.map((t) => (
            <button
              key={t.value}
              type="button"
              role="radio"
              aria-checked={tone === t.value}
              className="tone"
              data-on={tone === t.value}
              disabled={busy}
              onClick={() => setTone(t.value)}
            >
              <span className="tone__l">{t.label}</span>
              <span className="hint">{t.note}</span>
            </button>
          ))}
        </div>
        <ErrorBox error={error} />
        <div className="split mt">
          <button className="btn" onClick={write} disabled={busy || !session}>
            {busy ? t("letter.writing") : letter ? t("letter.rewrite") : t("letter.write")}
          </button>
          {busy ? (
            <button className="btn btn--ghost" onClick={() => abort.current?.abort()}>
              {t("letter.stop")}
            </button>
          ) : null}
        </div>
      </Row>

      {busy || showing ? (
        <Row
          margin={
            <>
              <span className="label">{t("letter.draft")}</span>
              {letter ? (
                <button className="btn btn--link" onClick={copy}>
                  {copied ? t("common.copied") : t("common.copy")}
                </button>
              ) : null}
            </>
          }
        >
          {/* The live region announces the stage, not every token: a screen
              reader reciting a letter three words at a time is unusable. */}
          <p className="hint" role="status" aria-live="polite">
            {stage ? <Spinner label={stage} /> : busy ? "Writing…" : ""}
          </p>

          <article className="letter" data-streaming={busy && !letter}>
            {showing.split("\n\n").filter(Boolean).map((para, i) => (
              <p key={i}>{para}</p>
            ))}
            {busy && !letter ? <span className="caret" aria-hidden="true" /> : null}
          </article>

          {letter?.claims_used.length ? (
            <div className="mt">
              <span className="label">{t("letter.builtFrom")}</span>
              <ul className="list list--bullet claims">
                {letter.claims_used.map((c) => <li key={c}>{c}</li>)}
              </ul>
              <p className="hint">
                Each of these was marked <em>Evidenced</em> in your gap analysis, with a
                quote from your CV behind it.
              </p>
            </div>
          ) : null}
        </Row>
      ) : null}

      <Row margin={<span className="label">{t("common.next")}</span>}>
        <div className="split">
          <Link className="btn btn--ghost" to={`/session/${session?.id}/scorecard`}>
            Back to the scorecard
          </Link>
          <Link className="btn btn--ghost" to={`/session/${session?.id}/coach`}>
            Ask the coach
          </Link>
        </div>
      </Row>
    </div>
  );
}
