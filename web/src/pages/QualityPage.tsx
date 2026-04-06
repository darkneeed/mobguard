import { useEffect, useState } from "react";

import { api } from "../api/client";

type QualityPayload = {
  open_cases: number;
  total_cases: number;
  resolved_home: number;
  resolved_mobile: number;
  skipped: number;
  resolution_total: number;
  active_learning_patterns: number;
  active_sessions: number;
  live_rules_revision: number;
  live_rules_updated_at: string;
  live_rules_updated_by: string;
  top_noisy_asns: Array<{ asn_key: string; cnt: number }>;
  top_patterns: Array<{
    pattern_type: string;
    pattern_value: string;
    decision: string;
    support: number;
    precision: number;
  }>;
};

export function QualityPage() {
  const [data, setData] = useState<QualityPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getQuality()
      .then((payload) => setData(payload as QualityPayload))
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Quality</span>
          <h1>Шумные ASN, объём ревью и активные паттерны</h1>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {!data ? <div className="panel">Loading…</div> : null}

      {data ? (
        <>
          <div className="stats-grid">
            <div className="stat-card"><span>Open cases</span><strong>{data.open_cases}</strong></div>
            <div className="stat-card"><span>Total cases</span><strong>{data.total_cases}</strong></div>
            <div className="stat-card"><span>Resolved HOME</span><strong>{data.resolved_home}</strong></div>
            <div className="stat-card"><span>Resolved MOBILE</span><strong>{data.resolved_mobile}</strong></div>
            <div className="stat-card"><span>Skipped</span><strong>{data.skipped}</strong></div>
            <div className="stat-card"><span>Active patterns</span><strong>{data.active_learning_patterns}</strong></div>
            <div className="stat-card"><span>Active sessions</span><strong>{data.active_sessions}</strong></div>
            <div className="stat-card">
              <span>HOME ratio</span>
              <strong>
                {data.resolution_total > 0
                  ? `${Math.round((data.resolved_home / data.resolution_total) * 100)}%`
                  : "0%"}
              </strong>
            </div>
            <div className="stat-card">
              <span>MOBILE ratio</span>
              <strong>
                {data.resolution_total > 0
                  ? `${Math.round((data.resolved_mobile / data.resolution_total) * 100)}%`
                  : "0%"}
              </strong>
            </div>
          </div>
          <div className="panel queue-footer">
            <span>Rules revision {data.live_rules_revision}</span>
            <span>Updated {data.live_rules_updated_at}</span>
            <span>By {data.live_rules_updated_by}</span>
          </div>
          <div className="panel">
            <h2>Top noisy ASN</h2>
            <ul className="reason-list">
              {data.top_noisy_asns.map((item) => (
                <li key={item.asn_key}>
                  <strong>{item.asn_key}</strong>
                  <span>{item.cnt} review cases</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <h2>Top promoted patterns</h2>
            <ul className="reason-list">
              {data.top_patterns.map((item) => (
                <li key={`${item.pattern_type}:${item.pattern_value}`}>
                  <strong>{item.pattern_type}:{item.pattern_value}</strong>
                  <span>
                    {item.decision} · support {item.support} · precision{" "}
                    {Math.round(item.precision * 100)}%
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </section>
  );
}
