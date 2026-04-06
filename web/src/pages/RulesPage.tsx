import { useEffect, useState } from "react";

import { api, RulesState } from "../api/client";

type RulesPayload = {
  admin_tg_ids?: number[];
  pure_mobile_asns?: number[];
  pure_home_asns?: number[];
  mixed_asns?: number[];
  allowed_isp_keywords?: string[];
  home_isp_keywords?: string[];
  exclude_isp_keywords?: string[];
  settings?: Record<string, string | number | boolean>;
};

const LIST_FIELDS: Array<keyof RulesPayload> = [
  "admin_tg_ids",
  "pure_mobile_asns",
  "pure_home_asns",
  "mixed_asns",
  "allowed_isp_keywords",
  "home_isp_keywords",
  "exclude_isp_keywords"
];

export function RulesPage() {
  const [state, setState] = useState<RulesState | null>(null);
  const [draft, setDraft] = useState<RulesPayload | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api
      .getRules()
      .then((payload) => {
        setState(payload);
        setDraft(payload.rules as RulesPayload);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const rules = draft;
  const dirty = JSON.stringify(draft) !== JSON.stringify(state?.rules || null);

  async function save() {
    if (!rules || !state) return;
    try {
      const payload: Record<string, unknown> = {
        settings: rules.settings || {}
      };
      for (const field of LIST_FIELDS) {
        const rawValue = (rules[field] || []) as Array<string | number>;
        payload[field] = rawValue.map((item) =>
          ["allowed_isp_keywords", "home_isp_keywords", "exclude_isp_keywords"].includes(field)
            ? String(item).trim()
            : Number(item)
        );
      }
      const updated = await api.updateRules({
        rules: payload,
        revision: state.revision,
        updated_at: state.updated_at
      });
      setState(updated);
      setDraft(updated.rules as RulesPayload);
      setError("");
      setSaved("Rules updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Live Rules</span>
          <h1>Редактирование порогов и списков без рестарта</h1>
        </div>
        <div className="action-row">
          <span className={dirty ? "tag review-only" : "tag severity-low"}>
            {dirty ? "unsaved changes" : "saved"}
          </span>
          <button disabled={!dirty} onClick={save}>Save rules</button>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {state ? (
        <div className="panel queue-footer">
          <span>Revision {state.revision}</span>
          <span>Updated at {state.updated_at || "n/a"}</span>
          <span>Updated by {state.updated_by || "n/a"}</span>
        </div>
      ) : null}
      {!rules ? <div className="panel">Loading…</div> : null}

      {rules ? (
        <div className="detail-grid">
          <div className="panel">
            <h2>Thresholds</h2>
            <div className="form-grid">
              {Object.entries(rules.settings || {})
                .filter(([key]) => key.includes("threshold") || key.includes("score"))
                .map(([key, value]) => (
                <label key={key}>
                  <span>{key}</span>
                  <input
                    value={String(value)}
                    onChange={(event) =>
                      setDraft((prev) => ({
                        ...(prev || {}),
                        settings: {
                          ...(prev?.settings || {}),
                          [key]:
                            value === true || value === false
                              ? event.target.value === "true"
                              : Number.isFinite(Number(value))
                                ? Number(event.target.value)
                                : event.target.value
                        }
                      }))
                    }
                  />
                </label>
              ))}
            </div>
          </div>

          <div className="panel">
            <h2>Policy Flags</h2>
            <div className="form-grid">
              {Object.entries(rules.settings || {})
                .filter(([key]) =>
                  [
                    "shadow_mode",
                    "probable_home_warning_only",
                    "auto_enforce_requires_hard_or_multi_signal",
                    "review_ui_base_url",
                    "learning_promote_asn_min_support",
                    "learning_promote_asn_min_precision",
                    "learning_promote_combo_min_support",
                    "learning_promote_combo_min_precision",
                    "live_rules_refresh_seconds"
                  ].includes(key)
                )
                .map(([key, value]) => (
                  <label key={key}>
                    <span>{key}</span>
                    <input
                      value={String(value)}
                      onChange={(event) =>
                        setDraft((prev) => ({
                          ...(prev || {}),
                          settings: {
                            ...(prev?.settings || {}),
                            [key]:
                              value === true || value === false
                                ? event.target.value === "true"
                                : Number.isFinite(Number(value))
                                  ? Number(event.target.value)
                                  : event.target.value
                          }
                        }))
                      }
                    />
                  </label>
                ))}
            </div>
          </div>

          {LIST_FIELDS.map((field) => (
            <div className="panel" key={field}>
              <h2>{field}</h2>
              <textarea
                className="note-box tall"
                value={((rules[field] || []) as Array<string | number>).join("\n")}
                onChange={(event) =>
                  setDraft((prev) => ({
                    ...(prev || {}),
                    [field]: event.target.value
                      .split("\n")
                      .map((item) => item.trim())
                      .filter(Boolean)
                  }))
                }
              />
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
