import { useEffect, useState } from "react";

import { api, RulesState } from "../api/client";
import { FieldLabel } from "../components/FieldLabel";
import {
  RULE_LIST_FIELDS,
  RULE_SETTING_FIELDS,
  RuleListFieldMeta,
  RuleSettingFieldMeta,
  RuleSettingValue,
  RulesDraft
} from "../rulesMeta";
import { formatDisplayDateTime } from "../utils/datetime";

type EnforcementPayload = {
  settings: Record<string, string | number | boolean | string[]>;
};

type GeneralSettingField = {
  key: string;
  label: string;
  description: string;
  inputType: "number" | "boolean" | "number-list";
  step?: number;
};

const GENERAL_SETTINGS_FIELDS: GeneralSettingField[] = [
  {
    key: "usage_time_threshold",
    label: "Minimum suspicious usage time (sec)",
    description: "How long a suspicious session must stay active before enforcement starts.",
    inputType: "number"
  },
  {
    key: "warning_timeout_seconds",
    label: "Warning cooldown (sec)",
    description: "Minimum delay before the next warning can be sent.",
    inputType: "number"
  },
  {
    key: "warnings_before_ban",
    label: "Warnings before first ban",
    description: "How many warning events are required before the first ban.",
    inputType: "number"
  },
  {
    key: "warning_only_mode",
    label: "Only warnings mode",
    description: "Never escalate to bans automatically.",
    inputType: "boolean"
  },
  {
    key: "manual_review_mixed_home_enabled",
    label: "Review mixed HOME cases manually",
    description: "Send mixed HOME outcomes to manual review before action.",
    inputType: "boolean"
  },
  {
    key: "manual_ban_approval_enabled",
    label: "Require admin approval for bans",
    description: "Pause ban execution until admin approves it.",
    inputType: "boolean"
  },
  {
    key: "dry_run",
    label: "Dry run",
    description: "Analyze and notify without applying remote disable actions.",
    inputType: "boolean"
  },
  {
    key: "ban_durations_minutes",
    label: "Ban durations ladder (minutes)",
    description: "One duration per line: first ban, second ban, third ban, and so on.",
    inputType: "number-list"
  }
];

const LIST_SECTIONS = Array.from(
  new Set(RULE_LIST_FIELDS.filter((field) => field.section !== "Access").map((field) => field.section))
);
const SETTING_SECTIONS = Array.from(new Set(RULE_SETTING_FIELDS.map((field) => field.section)));

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeRulesDraft(source: Record<string, unknown>): RulesDraft {
  const draft: RulesDraft = { settings: {} };
  const settings = isRecord(source.settings) ? source.settings : {};

  for (const field of RULE_LIST_FIELDS) {
    const rawValue = source[field.key];
    draft[field.key] = Array.isArray(rawValue) ? rawValue.map((item) => String(item)) : [];
  }

  for (const field of RULE_SETTING_FIELDS) {
    const rawValue = settings[field.key];
    if (
      typeof rawValue === "string" ||
      typeof rawValue === "number" ||
      typeof rawValue === "boolean"
    ) {
      draft.settings![field.key] = rawValue;
    }
  }

  return draft;
}

function normalizeGeneralSettingsDraft(source: Record<string, string | number | boolean | string[]>): Record<string, string> {
  return Object.fromEntries(
    GENERAL_SETTINGS_FIELDS.map((field) => {
      const rawValue = source[field.key];
      if (field.inputType === "number-list") {
        return [field.key, Array.isArray(rawValue) ? rawValue.map((item) => String(item)).join("\n") : ""];
      }
      return [field.key, String(rawValue ?? "")];
    })
  );
}

function listValuesToText(values: Array<string | number> | undefined): string {
  return (values || []).map((item) => String(item)).join("\n");
}

function parseListText(text: string): string[] {
  return text
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function serializeListField(meta: RuleListFieldMeta, values: Array<string | number> | undefined) {
  const rawValues = (values || []).map((item) => String(item).trim()).filter(Boolean);
  if (meta.itemType === "string") {
    return rawValues;
  }

  const serialized: number[] = [];
  for (const item of rawValues) {
    const parsed = Number(item);
    if (!Number.isFinite(parsed)) {
      throw new Error(`${meta.label}: invalid number '${item}'`);
    }
    serialized.push(parsed);
  }
  return serialized;
}

function serializeSettingField(meta: RuleSettingFieldMeta, value: RuleSettingValue) {
  if (meta.inputType === "boolean") {
    return Boolean(value);
  }
  if (meta.inputType === "text") {
    return String(value ?? "").trim();
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${meta.label}: invalid number`);
  }
  return parsed;
}

function serializeGeneralSettings(draft: Record<string, string>) {
  const payload: Record<string, unknown> = {};

  for (const field of GENERAL_SETTINGS_FIELDS) {
    const rawValue = draft[field.key] ?? "";
    if (field.inputType === "boolean") {
      payload[field.key] = rawValue === "true";
      continue;
    }
    if (field.inputType === "number-list") {
      payload[field.key] = rawValue
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean)
        .map((item) => {
          const parsed = Number(item);
          if (!Number.isFinite(parsed)) {
            throw new Error(`${field.label}: invalid value '${item}'`);
          }
          return parsed;
        });
      continue;
    }

    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed)) {
      throw new Error(`${field.label}: invalid number`);
    }
    payload[field.key] = parsed;
  }

  return payload;
}

function getSettingInputValue(meta: RuleSettingFieldMeta, value: RuleSettingValue): string {
  if (meta.inputType === "boolean") {
    return value === true ? "true" : "false";
  }
  return value === undefined || value === null ? "" : String(value);
}

function formatUpdatedBy(value: string | undefined): string {
  if (!value || value === "bootstrap") return "system";
  return value;
}

export function RulesPage() {
  const [state, setState] = useState<RulesState | null>(null);
  const [draft, setDraft] = useState<RulesDraft | null>(null);
  const [savedDraft, setSavedDraft] = useState<RulesDraft | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const [generalDraft, setGeneralDraft] = useState<Record<string, string> | null>(null);
  const [savedGeneralDraft, setSavedGeneralDraft] = useState<Record<string, string> | null>(null);
  const [generalError, setGeneralError] = useState("");
  const [generalSaved, setGeneralSaved] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [detectionPayload, enforcementPayload] = await Promise.all([
          api.getDetectionSettings(),
          api.getEnforcementSettings()
        ]);
        if (cancelled) return;

        const typedDetection = detectionPayload as RulesState;
        const normalizedRules = normalizeRulesDraft(typedDetection.rules);
        const typedEnforcement = enforcementPayload as EnforcementPayload;
        const normalizedGeneral = normalizeGeneralSettingsDraft(typedEnforcement.settings);

        setState(typedDetection);
        setDraft(normalizedRules);
        setSavedDraft(normalizedRules);
        setGeneralDraft(normalizedGeneral);
        setSavedGeneralDraft(normalizedGeneral);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load rules");
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const dirty = JSON.stringify(draft) !== JSON.stringify(savedDraft);
  const generalDirty = JSON.stringify(generalDraft) !== JSON.stringify(savedGeneralDraft);

  async function save() {
    if (!draft || !state) return;
    try {
      const payload: Record<string, unknown> = { settings: {} };

      for (const field of RULE_LIST_FIELDS) {
        payload[field.key] = serializeListField(field, draft[field.key]);
      }

      for (const field of RULE_SETTING_FIELDS) {
        payload.settings = {
          ...(payload.settings as Record<string, unknown>),
          [field.key]: serializeSettingField(field, draft.settings?.[field.key])
        };
      }

      const updated = (await api.updateDetectionSettings({
        rules: payload,
        revision: state.revision,
        updated_at: state.updated_at
      })) as RulesState;
      const normalized = normalizeRulesDraft(updated.rules);
      setState(updated);
      setDraft(normalized);
      setSavedDraft(normalized);
      setError("");
      setSaved("Rules updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaved("");
    }
  }

  async function saveGeneralSettings() {
    if (!generalDraft) return;
    try {
      const response = (await api.updateEnforcementSettings({
        settings: serializeGeneralSettings(generalDraft)
      })) as EnforcementPayload;
      const normalized = normalizeGeneralSettingsDraft(response.settings);
      setGeneralDraft(normalized);
      setSavedGeneralDraft(normalized);
      setGeneralError("");
      setGeneralSaved("General settings saved");
    } catch (err) {
      setGeneralError(err instanceof Error ? err.message : "Save failed");
      setGeneralSaved("");
    }
  }

  function updateListField(meta: RuleListFieldMeta, text: string) {
    setDraft((prev) => ({
      ...(prev || {}),
      [meta.key]: parseListText(text),
      settings: prev?.settings || {}
    }));
    setSaved("");
  }

  function updateSettingField(meta: RuleSettingFieldMeta, value: string) {
    setDraft((prev) => ({
      ...(prev || {}),
      settings: {
        ...(prev?.settings || {}),
        [meta.key]: meta.inputType === "boolean" ? value === "true" : value
      }
    }));
    setSaved("");
  }

  function updateGeneralField(key: string, value: string) {
    setGeneralDraft((prev) => ({
      ...(prev || {}),
      [key]: value
    }));
    setGeneralSaved("");
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Live Rules</span>
          <h1>Понятные live-настройки без редактирования сырых ключей</h1>
        </div>
        <div className="action-row">
          <span className={dirty ? "tag review-only" : "tag severity-low"}>
            {dirty ? "unsaved changes" : "saved"}
          </span>
          <button disabled={!dirty} onClick={save}>
            Save rules
          </button>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {state ? (
        <div className="panel queue-footer">
          <span>Revision {state.revision}</span>
          <span>Updated at {formatDisplayDateTime(state.updated_at, "n/a")}</span>
          <span>Updated by {formatUpdatedBy(state.updated_by)}</span>
        </div>
      ) : null}
      {!draft && !generalDraft ? <div className="panel">Loading…</div> : null}

      {generalDraft ? (
        <div className="panel">
          <div className="panel-heading panel-heading-row">
            <div>
              <h2>General settings</h2>
              <p className="muted">Runtime escalation and sanction controls.</p>
            </div>
            <div className="action-row">
              <span className={generalDirty ? "tag review-only" : "tag severity-low"}>
                {generalDirty ? "unsaved changes" : "saved"}
              </span>
              <button disabled={!generalDirty} onClick={saveGeneralSettings}>
                Save general settings
              </button>
            </div>
          </div>
          {generalError ? <div className="error-box">{generalError}</div> : null}
          {generalSaved ? <div className="ok-box">{generalSaved}</div> : null}
          <div className="form-grid">
            {GENERAL_SETTINGS_FIELDS.map((field) => (
              <div
                className={field.inputType === "number-list" ? "rule-field rule-field-wide" : "rule-field"}
                key={field.key}
              >
                <FieldLabel label={field.label} description={field.description} />
                {field.inputType === "boolean" ? (
                  <select
                    value={generalDraft[field.key] || "false"}
                    onChange={(event) => updateGeneralField(field.key, event.target.value)}
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                ) : field.inputType === "number-list" ? (
                  <textarea
                    className="note-box tall"
                    value={generalDraft[field.key] || ""}
                    onChange={(event) => updateGeneralField(field.key, event.target.value)}
                  />
                ) : (
                  <input
                    type="number"
                    step={field.step}
                    value={generalDraft[field.key] || ""}
                    onChange={(event) => updateGeneralField(field.key, event.target.value)}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {draft ? (
        <div className="page">
          {LIST_SECTIONS.map((section) => (
            <div className="panel" key={section}>
              <div className="panel-heading">
                <h2>{section}</h2>
                <p className="muted">Editable list-based rules.</p>
              </div>
              <div className="detail-grid">
                {RULE_LIST_FIELDS.filter((field) => field.section === section).map((field) => (
                  <div className="rule-field" key={field.key}>
                    <FieldLabel
                      label={field.label}
                      description={field.description}
                      recommendation={field.recommendation}
                    />
                    <textarea
                      className="note-box tall"
                      value={listValuesToText(draft[field.key])}
                      onChange={(event) => updateListField(field, event.target.value)}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}

          {SETTING_SECTIONS.map((section) => (
            <div className="panel" key={section}>
              <div className="panel-heading">
                <h2>{section}</h2>
                <p className="muted">Canonical editable settings only.</p>
              </div>
              <div className="form-grid">
                {RULE_SETTING_FIELDS.filter((field) => field.section === section).map((field) => (
                  <div className="rule-field" key={field.key}>
                    <FieldLabel
                      label={field.label}
                      description={field.description}
                      recommendation={field.recommendation}
                    />
                    {field.inputType === "boolean" ? (
                      <select
                        value={getSettingInputValue(field, draft.settings?.[field.key])}
                        onChange={(event) => updateSettingField(field, event.target.value)}
                      >
                        <option value="true">true</option>
                        <option value="false">false</option>
                      </select>
                    ) : (
                      <input
                        type={field.inputType === "number" ? "number" : "text"}
                        step={field.step}
                        value={getSettingInputValue(field, draft.settings?.[field.key])}
                        onChange={(event) => updateSettingField(field, event.target.value)}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
