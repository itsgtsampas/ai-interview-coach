import { useEffect, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";

import { api } from "../api/client";
import type { DocumentKind, DocumentOut, SessionOut } from "../api/types";
import { ErrorBox, Head, Row, Spinner } from "../components/bits";

interface Ctx { session: SessionOut | null; refresh: () => Promise<void> }

/** What a document looks like once it has been read and indexed. */
function ReadyState({ doc }: { doc: DocumentOut }) {
  return (
    <>
      <p style={{ margin: "0.5rem 0 0.2rem", fontWeight: 600 }}>{doc.original_filename}</p>
      <p className="hint" style={{ margin: 0 }}>
        {doc.source === "text"
          ? `${doc.char_count.toLocaleString()} characters`
          : `${doc.page_count} page${doc.page_count === 1 ? "" : "s"}`}{" "}
        · {doc.chunk_count} chunks indexed
      </p>
    </>
  );
}

function FilePicker({
  title, hint, doc, onPick, busy,
}: {
  title: string; hint: string;
  doc: DocumentOut | undefined; onPick: (f: File) => void; busy: boolean;
}) {
  const state = doc?.ingest_status === "ready" ? "ready"
    : doc?.ingest_status === "failed" ? "failed" : "idle";

  return (
    <div className="drop" data-state={state}>
      <div className="label">{title}</div>
      {doc?.ingest_status === "ready" ? (
        <ReadyState doc={doc} />
      ) : doc?.ingest_status === "failed" ? (
        <p style={{ margin: "0.5rem 0", fontSize: "0.85rem" }}>{doc.ingest_error}</p>
      ) : busy || doc ? (
        <p style={{ margin: "0.7rem 0" }}><Spinner label="Reading and indexing…" /></p>
      ) : (
        <p className="hint" style={{ margin: "0.5rem 0 0.7rem" }}>{hint}</p>
      )}

      <label className="drop__cta">
        {doc ? "Replace file" : "Choose a PDF"}
        <input
          type="file" accept="application/pdf"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onPick(f); e.target.value = ""; }}
        />
      </label>
    </div>
  );
}

export function Upload() {
  const { session, refresh } = useOutletContext<Ctx>();
  const [docs, setDocs] = useState<DocumentOut[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<DocumentKind | null>(null);
  const [analysing, setAnalysing] = useState(false);
  // Pasting is the default for a job description: it is read on a web page, so
  // demanding a PDF would send the user through print-to-PDF for nothing.
  const [jdAsFile, setJdAsFile] = useState(false);
  const [jdText, setJdText] = useState("");
  const navigate = useNavigate();

  const load = async () => {
    if (!session) return;
    setDocs(await api.listDocuments(session.id));
  };

  useEffect(() => { load(); }, [session?.id]);

  // Indexing runs as a background task, so poll until both documents settle.
  useEffect(() => {
    if (!session) return;
    const pending = docs.some(
      (d) => d.ingest_status === "pending" || d.ingest_status === "processing");
    if (!pending) return;
    const t = setTimeout(load, 700);
    return () => clearTimeout(t);
  }, [docs, session?.id]);

  async function upload(kind: DocumentKind, file: File) {
    if (!session) return;
    setBusy(kind); setError(null);
    try {
      await api.uploadDocument(session.id, kind, file);
      await load();
    } catch (err) { setError(err); } finally { setBusy(null); }
  }

  async function paste() {
    if (!session) return;
    setBusy("jd"); setError(null);
    try {
      const firstLine = jdText.trim().split("\n")[0]?.slice(0, 80).trim();
      await api.pasteDocument(session.id, "jd", jdText, firstLine || "Pasted job description");
      await load();
    } catch (err) { setError(err); } finally { setBusy(null); }
  }

  const cv = docs.find((d) => d.kind === "cv");
  const jd = docs.find((d) => d.kind === "jd");
  const ready = cv?.ingest_status === "ready" && jd?.ingest_status === "ready";

  async function analyse() {
    if (!session) return;
    setAnalysing(true); setError(null);
    try {
      await api.runAnalysis(session.id);
      await refresh();
      navigate(`/session/${session.id}/report`);
    } catch (err) { setError(err); setAnalysing(false); }
  }

  return (
    <div className="sheet">
      <Head margin={<span className="label">Stage 1</span>}>
        <h1 className="display h1">{session?.title ?? "Session"}</h1>
        <p className="prose" style={{ marginBottom: 0 }}>
          Your CV as a PDF, and the job description however you have it — pasted from
          the posting, or as a file.
        </p>
      </Head>

      <Row margin={<span className="label">Your CV</span>}>
        {cv ? (
          <p className="hint" style={{ margin: "0 0 0.7rem" }}>
            Started from the CV on <Link to="/profile">your profile</Link>. Replacing it
            here affects this application only.
          </p>
        ) : (
          <p className="hint" style={{ margin: "0 0 0.7rem" }}>
            Add a CV to <Link to="/profile">your profile</Link> and future sessions will
            start from it automatically.
          </p>
        )}
        <FilePicker
          title="CV" doc={cv} busy={busy === "cv"}
          hint="A text-based PDF — the kind where you can select the text in a reader. Scans are rejected rather than misread."
          onPick={(f) => upload("cv", f)}
        />
      </Row>

      <Row
        margin={
          <>
            <span className="label">Job description</span>
            {jd?.ingest_status !== "ready" ? (
              <button
                className="btn btn--link"
                onClick={() => { setJdAsFile(!jdAsFile); setError(null); }}
              >
                {jdAsFile ? "Paste text instead" : "Upload a PDF instead"}
              </button>
            ) : null}
          </>
        }
      >
        {jd?.ingest_status === "ready" ? (
          <div className="drop" data-state="ready">
            <div className="label">Job description</div>
            <ReadyState doc={jd} />
            <button
              className="drop__cta"
              style={{ background: "none", border: 0, padding: 0 }}
              onClick={() => { setJdText(""); setDocs(docs.filter((d) => d.kind !== "jd")); }}
            >
              Replace
            </button>
          </div>
        ) : jdAsFile ? (
          <FilePicker
            title="Job description" doc={jd} busy={busy === "jd"}
            hint="Save the posting as a PDF and choose it here."
            onPick={(f) => upload("jd", f)}
          />
        ) : (
          <>
            <textarea
              className="textarea"
              value={jdText}
              disabled={busy === "jd"}
              placeholder={
                "Paste the whole posting — requirements, responsibilities, nice-to-haves.\n\n" +
                "Select it on the job page, copy, and paste here. Formatting does not matter."
              }
              onChange={(e) => setJdText(e.target.value)}
            />
            <div className="split" style={{ marginTop: "0.7rem" }}>
              <button
                className="btn"
                onClick={paste}
                disabled={busy === "jd" || jdText.trim().length < 200}
              >
                {busy === "jd" ? "Reading…" : "Use this job description"}
              </button>
              <span className="hint">
                {jdText.trim().length < 200
                  ? `${jdText.trim().length} of 200 characters minimum`
                  : `${jdText.trim().length.toLocaleString()} characters`}
              </span>
            </div>
            {jd?.ingest_status === "failed" ? (
              <p className="error" role="alert">{jd.ingest_error}</p>
            ) : null}
          </>
        )}
        <ErrorBox error={error} />
      </Row>

      <Row margin={<span className="label">Next</span>}>
        <p className="prose">
          The analysis reads every requirement in the job description and searches your CV
          for evidence of each one.
        </p>
        <button className="btn" onClick={analyse} disabled={!ready || analysing}>
          {analysing ? "Analysing…" : "Run gap analysis"}
        </button>
        {!ready ? (
          <p className="hint" style={{ marginTop: "0.6rem" }}>
            Both documents are needed first.
          </p>
        ) : null}
      </Row>
    </div>
  );
}
