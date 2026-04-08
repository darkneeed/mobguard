import { useEffect, useState } from "react";

import { api } from "../api/client";
import { FieldLabel } from "../components/FieldLabel";
import { InfoTooltip } from "../components/InfoTooltip";

type TelegramPayload = {
  settings: Record<string, string | number | boolean>;
  capabilities: {
    admin_bot_enabled: boolean;
    user_bot_enabled: boolean;
  };
};

type EnforcementPayload = {
  settings: Record<string, string | number | boolean | string[]>;
};

type TelegramField = {
  key: string;
  label: string;
  section: "delivery" | "admin" | "user";
  type: "text" | "number" | "boolean";
  step?: number;
  description: string;
};

type TemplateField = {
  key: string;
  audience: "admin" | "user";
  label: string;
  description: string;
};

const TELEGRAM_FIELDS: TelegramField[] = [
  {
    key: "tg_admin_chat_id",
    label: "Admin chat destination",
    section: "delivery",
    type: "text",
    description: "Telegram chat id for admin notifications."
  },
  {
    key: "tg_topic_id",
    label: "Admin thread/topic",
    section: "delivery",
    type: "number",
    description: "Optional topic/thread id inside the admin chat."
  },
  {
    key: "telegram_message_min_interval_seconds",
    label: "Message interval (sec)",
    section: "delivery",
    type: "number",
    step: 0.1,
    description: "Minimum delay between Telegram sends."
  },
  {
    key: "telegram_admin_notifications_enabled",
    label: "Send admin notifications",
    section: "delivery",
    type: "boolean",
    description: "Master switch for all admin bot notifications."
  },
  {
    key: "telegram_user_notifications_enabled",
    label: "Send user notifications",
    section: "delivery",
    type: "boolean",
    description: "Master switch for all user-facing bot messages."
  },
  {
    key: "telegram_admin_commands_enabled",
    label: "Enable admin bot commands",
    section: "delivery",
    type: "boolean",
    description: "Allows Telegram admin command handlers to run."
  },
  {
    key: "telegram_notify_admin_review_enabled",
    label: "Notify review cases",
    section: "admin",
    type: "boolean",
    description: "Send admin messages when review/manual moderation is needed."
  },
  {
    key: "telegram_notify_admin_warning_only_enabled",
    label: "Notify warning-only cases",
    section: "admin",
    type: "boolean",
    description: "Send admin messages for non-escalating warning-only events."
  },
  {
    key: "telegram_notify_admin_warning_enabled",
    label: "Notify warnings",
    section: "admin",
    type: "boolean",
    description: "Send admin messages when a warning is issued."
  },
  {
    key: "telegram_notify_admin_ban_enabled",
    label: "Notify bans",
    section: "admin",
    type: "boolean",
    description: "Send admin messages when a ban is issued."
  },
  {
    key: "telegram_notify_user_warning_only_enabled",
    label: "Send warning-only messages",
    section: "user",
    type: "boolean",
    description: "Send user-facing messages for non-escalating warning-only events."
  },
  {
    key: "telegram_notify_user_warning_enabled",
    label: "Send warning messages",
    section: "user",
    type: "boolean",
    description: "Send user-facing messages when a warning is issued."
  },
  {
    key: "telegram_notify_user_ban_enabled",
    label: "Send ban messages",
    section: "user",
    type: "boolean",
    description: "Send user-facing messages when a ban is issued."
  }
];

const TEMPLATE_FIELDS: TemplateField[] = [
  {
    key: "user_warning_only_template",
    audience: "user",
    label: "Warning-only message",
    description: "User-facing message when the case is warning-only and does not escalate."
  },
  {
    key: "user_warning_template",
    audience: "user",
    label: "Warning message",
    description: "User-facing message for standard warnings before a ban."
  },
  {
    key: "user_ban_template",
    audience: "user",
    label: "Ban message",
    description: "User-facing message sent when a ban is applied."
  },
  {
    key: "admin_warning_only_template",
    audience: "admin",
    label: "Warning-only message",
    description: "Admin notification text for warning-only cases."
  },
  {
    key: "admin_warning_template",
    audience: "admin",
    label: "Warning message",
    description: "Admin notification text for warning events."
  },
  {
    key: "admin_ban_template",
    audience: "admin",
    label: "Ban message",
    description: "Admin notification text for ban events."
  },
  {
    key: "admin_review_template",
    audience: "admin",
    label: "Review message",
    description: "Admin notification text for review/manual moderation cases."
  }
];

function normalizeTelegramDraft(payload: TelegramPayload): Record<string, string> {
  return Object.fromEntries(
    TELEGRAM_FIELDS.map((field) => [field.key, String(payload.settings[field.key] ?? "")])
  );
}

function normalizeTemplateDraft(payload: EnforcementPayload): Record<string, string> {
  return Object.fromEntries(
    TEMPLATE_FIELDS.map((field) => [field.key, String(payload.settings[field.key] ?? "")])
  );
}

export function TelegramPage() {
  const [data, setData] = useState<TelegramPayload | null>(null);
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [savedSettings, setSavedSettings] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const [templates, setTemplates] = useState<Record<string, string>>({});
  const [savedTemplates, setSavedTemplates] = useState<Record<string, string>>({});
  const [templatesError, setTemplatesError] = useState("");
  const [templatesSaved, setTemplatesSaved] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [telegramPayload, enforcementPayload] = await Promise.all([
          api.getTelegramSettings(),
          api.getEnforcementSettings()
        ]);
        if (cancelled) return;

        const typedTelegram = telegramPayload as TelegramPayload;
        const normalizedTelegram = normalizeTelegramDraft(typedTelegram);
        const typedEnforcement = enforcementPayload as EnforcementPayload;
        const normalizedTemplates = normalizeTemplateDraft(typedEnforcement);

        setData(typedTelegram);
        setSettings(normalizedTelegram);
        setSavedSettings(normalizedTelegram);
        setTemplates(normalizedTemplates);
        setSavedTemplates(normalizedTemplates);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load Telegram settings");
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const runtimeDirty = JSON.stringify(settings) !== JSON.stringify(savedSettings);
  const templatesDirty = JSON.stringify(templates) !== JSON.stringify(savedTemplates);

  async function saveRuntime() {
    if (!data) return;
    try {
      const settingsPayload = Object.fromEntries(
        TELEGRAM_FIELDS.map((field) => {
          if (field.type === "boolean") {
            return [field.key, settings[field.key] === "true"];
          }
          if (field.type === "number") {
            const parsed = Number(settings[field.key]);
            if (!Number.isFinite(parsed)) {
              throw new Error(`${field.label}: invalid number`);
            }
            return [field.key, parsed];
          }
          return [field.key, settings[field.key]];
        })
      );
      const response = (await api.updateTelegramSettings({
        settings: settingsPayload
      })) as TelegramPayload;
      const normalized = normalizeTelegramDraft(response);
      setData(response);
      setSettings(normalized);
      setSavedSettings(normalized);
      setSaved("Telegram settings saved");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaved("");
    }
  }

  async function saveTemplates() {
    try {
      const response = (await api.updateEnforcementSettings({
        settings: Object.fromEntries(
          TEMPLATE_FIELDS.map((field) => [field.key, templates[field.key] ?? ""])
        )
      })) as EnforcementPayload;
      const normalized = normalizeTemplateDraft(response);
      setTemplates(normalized);
      setSavedTemplates(normalized);
      setTemplatesSaved("Message templates saved");
      setTemplatesError("");
    } catch (err) {
      setTemplatesError(err instanceof Error ? err.message : "Save failed");
      setTemplatesSaved("");
    }
  }

  function renderTelegramField(field: TelegramField) {
    return (
      <div className="rule-field" key={field.key}>
        <FieldLabel label={field.label} description={field.description} />
        {field.type === "boolean" ? (
          <select
            value={settings[field.key]}
            onChange={(event) =>
              setSettings((prev) => ({ ...prev, [field.key]: event.target.value }))
            }
          >
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
        ) : (
          <input
            type={field.type === "number" ? "number" : "text"}
            step={field.step}
            value={settings[field.key]}
            onChange={(event) =>
              setSettings((prev) => ({ ...prev, [field.key]: event.target.value }))
            }
          />
        )}
      </div>
    );
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Telegram</span>
          <h1>Bot runtime settings and message delivery</h1>
        </div>
        <div className="action-row">
          <span className={runtimeDirty ? "tag review-only" : "tag severity-low"}>
            {runtimeDirty ? "unsaved changes" : "saved"}
          </span>
          <button onClick={saveRuntime} disabled={!data || !runtimeDirty}>
            Save telegram settings
          </button>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {!data ? <div className="panel">Loading…</div> : null}

      {data ? (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <span>Admin bot</span>
              <strong>{data.capabilities.admin_bot_enabled ? "ON" : "OFF"}</strong>
            </div>
            <div className="stat-card">
              <span>User bot</span>
              <strong>{data.capabilities.user_bot_enabled ? "ON" : "OFF"}</strong>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Telegram capability status</h2>
              <p className="muted">Bot tokens and usernames are managed only through `.env` on the server.</p>
            </div>
            <div className="stats-grid">
              <div className="stat-card">
                <span>Admin bot token + username</span>
                <strong>{data.capabilities.admin_bot_enabled ? "Configured" : "Disabled"}</strong>
              </div>
              <div className="stat-card">
                <span>User bot token</span>
                <strong>{data.capabilities.user_bot_enabled ? "Configured" : "Disabled"}</strong>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Delivery & bot behavior</h2>
              <p className="muted">These settings are live-editable and do not require restart.</p>
            </div>
            <div className="form-grid">
              {TELEGRAM_FIELDS.filter((field) => field.section === "delivery").map(renderTelegramField)}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Admin notifications</h2>
              <p className="muted">Per-event delivery controls for the admin bot.</p>
            </div>
            <div className="form-grid">
              {TELEGRAM_FIELDS.filter((field) => field.section === "admin").map(renderTelegramField)}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>User notifications</h2>
              <p className="muted">Per-event delivery controls for user-facing bot messages.</p>
            </div>
            <div className="form-grid">
              {TELEGRAM_FIELDS.filter((field) => field.section === "user").map(renderTelegramField)}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div className="action-row">
                <h2>Message templates</h2>
                <InfoTooltip
                  label="Message templates hint"
                  content={
                    "Multiline text is preserved.\n\nPlaceholders: {{username}}, {{warning_count}}, {{warnings_left}}, {{ban_text}}, {{review_url}}."
                  }
                />
              </div>
              <div className="action-row">
                <span className={templatesDirty ? "tag review-only" : "tag severity-low"}>
                  {templatesDirty ? "unsaved changes" : "saved"}
                </span>
                <button disabled={!templatesDirty} onClick={saveTemplates}>
                  Save message templates
                </button>
              </div>
            </div>
            {templatesError ? <div className="error-box">{templatesError}</div> : null}
            {templatesSaved ? <div className="ok-box">{templatesSaved}</div> : null}
            <div className="detail-grid">
              {(["user", "admin"] as const).map((audience) => (
                <div className="settings-group" key={audience}>
                  <h3>{audience === "user" ? "User templates" : "Admin templates"}</h3>
                  <div className="settings-group-fields">
                    {TEMPLATE_FIELDS.filter((field) => field.audience === audience).map((field) => (
                      <div className="rule-field" key={field.key}>
                        <FieldLabel label={field.label} description={field.description} />
                        <textarea
                          className="note-box tall"
                          value={templates[field.key] || ""}
                          onChange={(event) =>
                            setTemplates((prev) => ({ ...prev, [field.key]: event.target.value }))
                          }
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
