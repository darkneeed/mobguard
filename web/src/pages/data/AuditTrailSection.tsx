import { AuditTrailResponse } from "../../api/client";
import type { Language } from "../../localization/types";
import { formatDisplayDateTime } from "../../utils/datetime";

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

type Props = {
  t: TranslateFn;
  language: Language;
  audit: AuditTrailResponse | null;
};

export function AuditTrailSection({ t, language, audit }: Props) {
  const items = audit?.items || [];
  return (
    <div className="panel">
      <div className="panel-heading">
        <h2>{t("data.audit.title")}</h2>
        <p className="muted">{t("data.audit.description")}</p>
      </div>
      <div className="record-list">
        {items.length === 0 ? <div className="provider-empty"><span>{t("data.audit.empty")}</span></div> : null}
        {items.map((item) => (
          <div className="record-item" key={String(item.id)}>
            <div className="record-main">
              <span className="record-title">{item.action}</span>
              <span className="tag">{item.actor_role}</span>
            </div>
            <div className="record-meta">
              <span>{item.actor_username || item.actor_subject}</span>
              <span>{item.target_type}:{item.target_id}</span>
              <span>{formatDisplayDateTime(item.created_at, t("common.notAvailable"), language)}</span>
            </div>
            <pre className="log-box">{JSON.stringify(item.details || {}, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
