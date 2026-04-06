import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";

type ReviewPayload = Record<string, unknown> & {
  latest_event?: Record<string, unknown> & { bundle?: Record<string, unknown> };
  resolutions?: Array<Record<string, unknown>>;
  related_cases?: Array<Record<string, unknown>>;
};

export function ReviewDetailPage() {
  const { caseId = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<ReviewPayload | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getReview(caseId)
      .then((payload) => setData(payload as ReviewPayload))
      .catch((err: Error) => setError(err.message));
  }, [caseId]);

  async function resolve(resolution: string) {
    try {
      await api.resolveReview(caseId, resolution, note);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed");
    }
  }

  const bundle = data?.latest_event?.bundle;
  const reasons = Array.isArray(bundle?.reasons) ? bundle?.reasons : [];
  const relatedCases = Array.isArray(data?.related_cases) ? data.related_cases : [];
  const resolutions = Array.isArray(data?.resolutions) ? data.resolutions : [];

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Case Detail</span>
          <h1>Review case #{caseId}</h1>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {!data ? <div className="panel">Loading…</div> : null}

      {data ? (
        <div className="detail-grid">
          <div className="panel">
            <h2>Summary</h2>
            <dl className="detail-list">
              <div><dt>User</dt><dd>{String(data.username || data.uuid || "N/A")}</dd></div>
              <div><dt>IP</dt><dd>{String(data.ip || "N/A")}</dd></div>
              <div><dt>Tag</dt><dd>{String(data.tag || "N/A")}</dd></div>
              <div><dt>Verdict</dt><dd>{String(data.verdict || "N/A")}</dd></div>
              <div><dt>Confidence</dt><dd>{String(data.confidence_band || "N/A")}</dd></div>
              <div><dt>Punitive</dt><dd>{Number(data.punitive_eligible || 0) ? "yes" : "no"}</dd></div>
              <div><dt>ISP</dt><dd>{String(data.isp || "N/A")}</dd></div>
              <div><dt>Review URL</dt><dd>{String(data.review_url || "N/A")}</dd></div>
            </dl>
          </div>

          <div className="panel">
            <h2>Reasons</h2>
            <ul className="reason-list">
              {reasons.map((reason, index) => {
                const item = reason as Record<string, unknown>;
                return (
                  <li key={`${String(item.code)}-${index}`}>
                    <strong>{String(item.code)}</strong>
                    <span>{String(item.message || "")}</span>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="panel">
            <h2>Log</h2>
            <pre className="log-box">{Array.isArray(bundle?.log) ? bundle?.log.join("\n") : ""}</pre>
          </div>

          <div className="panel">
            <h2>Resolution history</h2>
            <ul className="reason-list">
              {resolutions.length === 0 ? <li><span>No resolutions yet</span></li> : null}
              {resolutions.map((resolution) => (
                <li key={String(resolution.id)}>
                  <strong>{String(resolution.resolution)}</strong>
                  <span>
                    {String(resolution.actor || "unknown")} · {String(resolution.created_at || "")}
                  </span>
                  <span>{String(resolution.note || "")}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h2>Linked user/IP context</h2>
            <ul className="reason-list">
              {relatedCases.length === 0 ? <li><span>No related cases found</span></li> : null}
              {relatedCases.map((item) => (
                <li key={String(item.id)}>
                  <strong>Case #{String(item.id)}</strong>
                  <span>
                    {String(item.ip)} · {String(item.verdict)} / {String(item.confidence_band)}
                  </span>
                  <span>{String(item.updated_at)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h2>Resolution</h2>
            <textarea
              className="note-box"
              placeholder="Комментарий для аудита"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <div className="action-row">
              <button onClick={() => resolve("MOBILE")}>Mark MOBILE</button>
              <button onClick={() => resolve("HOME")}>Mark HOME</button>
              <button className="ghost" onClick={() => resolve("SKIP")}>
                Skip
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
