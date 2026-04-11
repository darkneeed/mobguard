import { useEffect, useState } from "react";

import { api, ModuleRecord } from "../api/client";
import { useI18n } from "../localization";
import { formatDisplayDateTime } from "../utils/datetime";

type ModulesPayload = {
  items: ModuleRecord[];
  count: number;
};

export function ModulesPage() {
  const { t, language } = useI18n();
  const [data, setData] = useState<ModulesPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getModules()
      .then((payload) => setData(payload as ModulesPayload))
      .catch((err: Error) => setError(err.message || t("modules.loadFailed")));
  }, [t]);

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <span className="eyebrow">{t("modules.eyebrow")}</span>
          <h1>{t("modules.title")}</h1>
          <p className="page-lede">{t("modules.description")}</p>
        </div>
        <div className="dashboard-meta">
          <span className="chip">{t("modules.count", { count: data?.count ?? 0 })}</span>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="stats-grid">
        <div className="stat-card">
          <span>{t("modules.cards.total")}</span>
          <strong>{data?.count ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <span>{t("modules.cards.healthy")}</span>
          <strong>{data ? data.items.filter((item) => item.healthy).length : "—"}</strong>
        </div>
        <div className="stat-card">
          <span>{t("modules.cards.openCases")}</span>
          <strong>
            {data ? data.items.reduce((sum, item) => sum + Number(item.open_review_cases || 0), 0) : "—"}
          </strong>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <h2>{t("modules.listTitle")}</h2>
          <p className="muted">{t("modules.listDescription")}</p>
        </div>
        <div className="queue-grid">
          {(data?.items || []).map((item) => (
            <article className="queue-card" key={item.module_id}>
              <div className="queue-card-top">
                <strong>{item.module_name}</strong>
                <span className={`status-badge ${item.healthy ? "status-resolved" : "severity-high"}`}>
                  {item.healthy ? t("modules.healthy") : t("modules.stale")}
                </span>
              </div>
              <div className="queue-card-identifiers">
                <span>ID: {item.module_id}</span>
                <span>{t("modules.version", { value: item.version || t("common.notAvailable") })}</span>
                <span>{t("modules.protocol", { value: item.protocol_version || "v1" })}</span>
              </div>
              <div className="queue-card-stack">
                <div className="queue-card-meta">
                  <span>{t("modules.lastSeen")}</span>
                  <strong>{formatDisplayDateTime(item.last_seen_at, t("common.notAvailable"), language)}</strong>
                </div>
                <div className="queue-card-meta">
                  <span>{t("modules.appliedRevision")}</span>
                  <strong>{item.config_revision_applied}</strong>
                </div>
                <div className="queue-card-meta">
                  <span>{t("modules.openCases")}</span>
                  <strong>{item.open_review_cases ?? 0}</strong>
                </div>
                <div className="queue-card-meta">
                  <span>{t("modules.analysisEvents")}</span>
                  <strong>{item.analysis_events_count ?? 0}</strong>
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
