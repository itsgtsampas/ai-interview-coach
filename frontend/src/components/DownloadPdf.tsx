import { useState } from "react";

import { api } from "../api/client";
import { ErrorBox, Spinner } from "./bits";

/** Download the scorecard.
 *
 *  Not an <a href>: the endpoint requires the Authorization header, so the file
 *  is fetched as a blob and handed to a synthetic link. The object URL is
 *  revoked straight after — a forgotten one pins the whole PDF in memory for
 *  the life of the tab.
 */
export function DownloadPdf({ sessionId }: { sessionId: number }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function download() {
    setBusy(true);
    setError(null);
    try {
      const { url, filename } = await api.scorecardPdf(sessionId);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button className="btn btn--ghost" onClick={download} disabled={busy}>
        {busy ? <Spinner label="Building…" /> : (
          <>
            <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true"
                 className="btn__icon">
              <path d="M8 1v9m0 0L4.5 6.5M8 10l3.5-3.5M2 13h12"
                    fill="none" stroke="currentColor" strokeWidth="1.6"
                    strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Download PDF
          </>
        )}
      </button>
      <ErrorBox error={error} />
    </>
  );
}
