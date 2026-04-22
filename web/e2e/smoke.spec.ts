import { expect, Page, Route, test } from "@playwright/test";

const ownerSession = {
  telegram_id: 1,
  username: "owner",
  first_name: "Owner",
  expires_at: "2026-04-22T12:00:00Z",
  subject: "local:owner",
  auth_method: "local",
  role: "owner",
  permissions: [
    "overview.read",
    "quality.read",
    "reviews.read",
    "reviews.resolve",
    "reviews.recheck",
    "rules.read",
    "rules.write",
    "settings.telegram.read",
    "settings.telegram.write",
    "settings.enforcement.read",
    "settings.enforcement.write",
    "settings.access.read",
    "settings.access.write",
    "data.read",
    "data.write",
    "modules.read",
    "modules.write",
    "modules.token_reveal",
    "audit.read",
  ],
  totp_enabled: true,
  totp_verified: true,
  totp_verified_at: "2026-04-22T11:59:00Z",
  payload: {},
};

const viewerSession = {
  telegram_id: 3,
  username: "viewer",
  first_name: "Viewer",
  expires_at: "2026-04-22T12:00:00Z",
  subject: "tg:3",
  auth_method: "telegram",
  role: "viewer",
  permissions: ["overview.read", "quality.read", "reviews.read", "data.read", "modules.read", "audit.read"],
  totp_enabled: false,
  totp_verified: false,
  totp_verified_at: "",
  payload: {},
};

const healthPayload = {
  status: "ok",
  core: { status: "ok", mode: "embedded", updated_at: "2026-04-22T12:00:00Z" },
  db: { healthy: true, path: "/runtime/bans.db" },
};

const qualityPayload = {
  open_cases: 1,
  total_cases: 5,
  resolved_home: 2,
  resolved_mobile: 2,
  skipped: 1,
  active_learning_patterns: 3,
  active_sessions: 1,
  live_rules_revision: 4,
  live_rules_updated_at: "2026-04-22T12:00:00Z",
  live_rules_updated_by: "owner",
  top_noisy_asns: [],
  mixed_providers: {
    open_cases: 0,
    conflict_cases: 0,
    conflict_rate: 0,
    top_open_cases: [],
  },
  learning: {
    promoted: {
      active_patterns: 3,
    },
  },
};

const reviewListPayload = {
  items: [
    {
      id: 1,
      status: "OPEN",
      review_reason: "provider_conflict",
      module_id: "module-1",
      module_name: "Node A",
      uuid: "uuid-1",
      username: "alice",
      system_id: 10,
      telegram_id: "11",
      ip: "1.1.1.1",
      tag: null,
      verdict: "UNSURE",
      confidence_band: "UNSURE",
      score: 42,
      isp: "ISP A",
      asn: 123,
      punitive_eligible: 1,
      severity: "critical",
      repeat_count: 2,
      reason_codes: ["provider_conflict"],
      opened_at: "2026-04-22T12:00:00Z",
      updated_at: "2026-04-22T12:00:00Z",
      review_url: "https://example.test/reviews/1",
    },
  ],
  count: 1,
  page: 1,
  page_size: 24,
};

const rulesPayload = {
  revision: 4,
  updated_at: "2026-04-22T12:00:00Z",
  updated_by: "owner",
  rules: {
    pure_mobile_asns: [2500],
    pure_home_asns: [],
    mixed_asns: [],
    allowed_isp_keywords: ["lte"],
    home_isp_keywords: [],
    exclude_isp_keywords: [],
    admin_tg_ids: [1],
    moderator_tg_ids: [2],
    viewer_tg_ids: [3],
    provider_profiles: [],
    settings: {
      threshold_mobile: 60,
      threshold_probable_mobile: 45,
      threshold_home: -60,
      threshold_probable_home: -45,
      pure_asn_score: 60,
      mixed_asn_score: 15,
      ptr_home_penalty: -20,
      mobile_kw_bonus: 20,
      provider_mobile_marker_bonus: 18,
      provider_home_marker_penalty: -18,
      ip_api_mobile_bonus: 10,
      pure_home_asn_penalty: -60,
      score_subnet_mobile_bonus: 0,
      score_subnet_home_penalty: 0,
      score_churn_high_bonus: 30,
      score_churn_medium_bonus: 15,
      score_stationary_penalty: -15,
      concurrency_threshold: 2,
      churn_window_hours: 4,
      churn_mobile_threshold: 4,
      lifetime_stationary_hours: 12,
      subnet_mobile_ttl_days: 7,
      subnet_home_ttl_days: 7,
      subnet_mobile_min_evidence: 3,
      subnet_home_min_evidence: 3,
      shadow_mode: true,
      probable_home_warning_only: true,
      auto_enforce_requires_hard_or_multi_signal: true,
      provider_conflict_review_only: true,
      review_ui_base_url: "",
      learning_promote_asn_min_support: 10,
      learning_promote_asn_min_precision: 0.95,
      learning_promote_combo_min_support: 5,
      learning_promote_combo_min_precision: 0.9,
      live_rules_refresh_seconds: 15,
      db_cleanup_interval_minutes: 30,
      module_heartbeats_retention_days: 14,
      ingested_raw_events_retention_days: 30,
      ip_history_retention_days: 30,
      orphan_analysis_events_retention_days: 30,
      resolved_review_retention_days: 30,
    },
  },
};

const enforcementPayload = {
  settings: {
    usage_time_threshold: 900,
    warning_timeout_seconds: 900,
    warnings_before_ban: 3,
    ban_durations_minutes: [15, 60, 1440],
    warning_only_mode: false,
    manual_review_mixed_home_enabled: false,
    manual_ban_approval_enabled: false,
    dry_run: true,
    report_time: "06:00",
    full_access_squad_name: "FULL",
    restricted_access_squad_name: "MOBILE_BLOCKED",
    traffic_cap_increment_gb: 10,
    traffic_cap_threshold_gb: 100,
    user_warning_only_template: "",
    user_warning_template: "",
    user_ban_template: "",
    admin_warning_only_template: "",
    admin_warning_template: "",
    admin_ban_template: "",
    admin_review_template: "",
  },
};

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

async function installApiStubs(page: Page, session: Record<string, unknown> | null) {
  await page.addInitScript(() => {
    window.localStorage.setItem("mobguard_language", "en");
  });
  let currentRules = JSON.parse(JSON.stringify(rulesPayload));
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/admin/me") {
      if (!session) {
        await fulfillJson(route, { detail: "Missing session cookie" }, 401);
        return;
      }
      await fulfillJson(route, session);
      return;
    }
    if (path === "/api/admin/logout") {
      await fulfillJson(route, { ok: true });
      return;
    }
    if (path === "/api/health") {
      await fulfillJson(route, healthPayload);
      return;
    }
    if (path === "/api/admin/metrics/quality") {
      await fulfillJson(route, qualityPayload);
      return;
    }
    if (path === "/api/admin/reviews" && request.method() === "GET") {
      await fulfillJson(route, reviewListPayload);
      return;
    }
    if (path === "/api/admin/reviews/1/resolve") {
      await fulfillJson(route, { id: 1, status: "RESOLVED" });
      return;
    }
    if (path === "/api/admin/reviews/recheck") {
      await fulfillJson(route, { count: 1, summary: { processed: 1 } });
      return;
    }
    if (path === "/api/admin/settings/detection" && request.method() === "GET") {
      await fulfillJson(route, currentRules);
      return;
    }
    if (path === "/api/admin/settings/detection" && request.method() === "PUT") {
      const body = JSON.parse(request.postData() || "{}");
      currentRules = {
        ...currentRules,
        revision: currentRules.revision + 1,
        updated_at: "2026-04-22T12:05:00Z",
        updated_by: "owner",
        rules: {
          ...currentRules.rules,
          ...body.rules,
        },
      };
      await fulfillJson(route, currentRules);
      return;
    }
    if (path === "/api/admin/settings/enforcement" && request.method() === "GET") {
      await fulfillJson(route, enforcementPayload);
      return;
    }
    if (path === "/api/admin/settings/enforcement" && request.method() === "PUT") {
      await fulfillJson(route, enforcementPayload);
      return;
    }
    if (path === "/api/admin/modules" && request.method() === "GET") {
      await fulfillJson(route, {
        items: [
          {
            module_id: "module-1",
            module_name: "Node A",
            status: "online",
            version: "1.0.0",
            protocol_version: "v1",
            config_revision_applied: 4,
            install_state: "online",
            managed: true,
            inbound_tags: ["DEFAULT-INBOUND"],
            health_status: "ok",
            error_text: "",
            last_validation_at: "2026-04-22T12:00:00Z",
            spool_depth: 0,
            access_log_exists: true,
            token_reveal_available: true,
            last_seen_at: "2026-04-22T12:00:00Z",
            healthy: true,
            open_review_cases: 0,
            analysis_events_count: 0,
          },
        ],
        count: 1,
      });
      return;
    }
    if (path === "/api/admin/modules/module-1" && request.method() === "GET") {
      await fulfillJson(route, {
        module: {
          module_id: "module-1",
          module_name: "Node A",
          status: "online",
          version: "1.0.0",
          protocol_version: "v1",
          config_revision_applied: 4,
          install_state: "online",
          managed: true,
          inbound_tags: ["DEFAULT-INBOUND"],
          health_status: "ok",
          error_text: "",
          last_validation_at: "2026-04-22T12:00:00Z",
          spool_depth: 0,
          access_log_exists: true,
          token_reveal_available: true,
          last_seen_at: "2026-04-22T12:00:00Z",
          healthy: true,
          open_review_cases: 0,
          analysis_events_count: 0,
        },
        install: {
          compose_yaml: "MODULE_TOKEN=__PASTE_TOKEN__",
        },
      });
      return;
    }
    if (path === "/api/admin/modules/module-1/token/reveal") {
      await fulfillJson(route, { module_id: "module-1", module_token: "revealed-token" });
      return;
    }
    if (path === "/api/admin/data/exports/calibration/preview") {
      await fulfillJson(route, {
        schema_version: 1,
        generated_at: "2026-04-22T12:00:00Z",
        snapshot_source: "live_rules",
        dataset_ready: true,
        tuning_ready: true,
        warnings: [],
        readiness: {
          overall_percent: 100,
          dataset_percent: 100,
          tuning_percent: 100,
          blockers: [],
          checks: [],
        },
        filters: { status: "resolved_only", include_unknown: false },
        row_counts: { raw_rows: 5, known_rows: 5, unknown_rows: 0 },
        coverage: { provider_profiles_count: 1, provider_key_coverage: 1, provider_pattern_candidates: 1 },
      });
      return;
    }
    if (path === "/api/admin/auth/telegram/start") {
      await fulfillJson(route, {
        telegram_enabled: false,
        bot_username: "",
        local_enabled: true,
        local_username_hint: "owner",
        review_ui_base_url: "",
        panel_name: "MobGuard",
        panel_logo_url: "",
      });
      return;
    }
    if (path === "/api/admin/auth/local/login") {
      await fulfillJson(route, {
        requires_totp: true,
        totp_setup_required: true,
        challenge_token: "challenge-token",
        subject: "local:owner",
        auth_method: "local",
        role: "owner",
      });
      return;
    }
    if (path === "/api/admin/auth/totp/setup") {
      await fulfillJson(route, {
        challenge_token: "challenge-token",
        secret: "JBSWY3DPEHPK3PXP",
        provisioning_uri: "otpauth://totp/MobGuard:owner?secret=JBSWY3DPEHPK3PXP&issuer=MobGuard",
        account_name: "owner",
        issuer: "MobGuard",
      });
      return;
    }
    if (path === "/api/admin/auth/totp/confirm") {
      await fulfillJson(route, ownerSession);
      return;
    }
    await route.abort();
  });
}

test("owner local login completes TOTP setup and lands in the panel", async ({ page }) => {
  await installApiStubs(page, null);
  await page.goto("/");

  await page.getByPlaceholder("Username").fill("owner");
  await page.getByPlaceholder("Password").fill("secret");
  await page.getByRole("button", { name: "Login" }).click();

  await expect(page.getByText("Set up owner TOTP")).toBeVisible();
  await page.getByPlaceholder("123456").fill("123456");
  await page.getByRole("button", { name: "Confirm TOTP setup" }).click();
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole("button", { name: "Logout" })).toBeVisible();
});

test("viewer is redirected away from owner-only routes", async ({ page }) => {
  await installApiStubs(page, viewerSession);
  await page.goto("/rules/policy");
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole("button", { name: "Logout" })).toBeVisible();
});

test("queue supports saved filters and quick resolve", async ({ page }) => {
  await installApiStubs(page, ownerSession);
  await page.goto("/queue");

  await expect(page.getByText("alice")).toBeVisible();
  await page.getByRole("button", { name: "Filters", exact: true }).click();
  await page.locator(".filter-drawer").getByPlaceholder("Username").fill("alice");
  await page.getByRole("button", { name: "Save current" }).click();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await page.getByRole("button", { name: "Apply saved" }).click();
  await expect(page.locator(".filter-drawer").getByPlaceholder("Username")).toHaveValue("alice");

  await page.locator(".queue-card").first().getByRole("button", { name: "Mobile", exact: true }).click();
  await expect(page.getByText("Review decision saved")).toBeVisible();
});

test("owner can save rules changes", async ({ page }) => {
  await installApiStubs(page, ownerSession);
  await page.goto("/rules/lists");

  await page.locator("textarea").first().fill("2500\n2501");
  await page.getByRole("button", { name: "Save rules" }).click();
  await expect(page.getByText("Rules updated")).toBeVisible();
});

test("owner can reveal module token and review calibration preview", async ({ page }) => {
  await installApiStubs(page, ownerSession);
  await page.goto("/modules");
  await page.getByRole("button", { name: "Open details" }).click();
  await page.getByRole("button", { name: "Reveal token" }).click();
  await expect(page.getByText("revealed-token")).toBeVisible();

  await page.goto("/data/exports");
  await expect(page.getByText("Calibration readiness")).toBeVisible();
  await expect(page.getByText("100%").first()).toBeVisible();
});
