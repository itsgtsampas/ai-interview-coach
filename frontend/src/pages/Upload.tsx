import { useEffect, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";

import { api } from "../api/client";
import type { DocumentKind, DocumentOut, SessionOut } from "../api/types";
import { ErrorBox, Head, Row, Spinner } from "../components/bits";

interface Ctx { session: SessionOut | null; refresh: () => Promise<void> }

function Dropzone({
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
        <>
          <p style={{ margin: "0.5rem 0 0.2rem", fontWeight: 600 }}>{doc.original_filename}</p>
          <p className="hint" style={{ margin: 0 }}>
            {doc.page_count} page{doc.page_count === 1 ? "" : "s"} · {doc.chunk_count} chunks indexed
          </p>
        </>
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
  const navigate = useNavigate();

  const load = async () => {
    if (!session) return;
    setDocs(await api.listDocuments(session.id));
  };

  useEffect(() => { load(); }, [session?.id]);

  // Indexing runs as a background task, so poll until both documents settle.
  useEffect(() => {
    if (!session) return;
    const pending = docs.some((d) => d.ingest_status === "pending" || d.ingest_status === "processing");
    if (!pending) return;
    const t = setTimeout(load, 700);
    return () => clearTimeout(t);
  }, [docs, session?.id]);

  async function upload(kind: DocumentKind, file: File) {
    if (!session) return;
    setBusy(kind);
    setError(null);
    try {
      await api.uploadDocument(session.id, kind, file);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  const cv = docs.find((d) => d.kind === "cv");
  const jd = docs.find((d) => d.kind === "jd");
  const ready = cv?.ingest_status === "ready" && jd?.ingest_status === "ready";

  async function analyse() {
    if (!session) return;
    setAnalysing(true);
    setError(null);
    try {
      await api.runAnalysis(session.id);
      await refresh();
      navigate(`/session/${session.id}/report`);
    } catch (err) {
      setError(err);
      setAnalysing(false);
    }
  }

  return (
    <div className="sheet">
      <Head margin={<span className="label">Stage 1</span>}>
        <h1 className="display h1">{session?.title ?? "Session"}</h1>
        <p className="prose" style={{ marginBottom: 0 }}>
          Both documents must be text-based PDFs — the kind where you can select the text
          in a reader. Scans are rejected rather than silently misread.
        </p>
      </Head>

      <Row margin={<span className="label">Documents</span>}>
        <div className="cards">
          <Dropzone
            title="Your CV" doc={cv} busy={busy === "cv"}
            hint="The CV you would actually send for this role."
            onPick={(f) => upload("cv", f)}
          />
          <Dropzone
            title="Job description" doc={jd} busy={busy === "jd"}
            hint="Save the posting as a PDF and upload it here."
            onPick={(f) => upload("jd", f)}
          />
        </div>
        <ErrorBox error={error} />
      </Row>

      <Row margin={<span className="label">Next</span>}>
        <p className="prose">
          The analysis reads every requirement in the job description and searches your CV
          for evidence of each one. It takes a moment.
        </p>
        <button className="btn" onClick={analyse} disabled={!ready || analysing}>
          {analysing ? "Analysing…" : "Run gap analysis"}
        </button>
        {!ready ? (
          <p className="hint" style={{ marginTop: "0.6rem" }}>
            Upload both documents first.
          </p>
        ) : null}
      </Row>
    </div>
  );
}
