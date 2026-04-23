type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

export type ReviewScopeType = "ip_device" | "subject_ip" | "ip_only";

export type ScopeContextPresentation = {
  scopeType: ReviewScopeType;
  decisionTarget: string;
  contextLabel: string;
  contextValue: string;
  historyTitle: string;
  historyLabel: string;
  scopeMeta: string;
};

export function normalizeReviewScopeType(value: string | null | undefined): ReviewScopeType {
  if (value === "ip_device" || value === "subject_ip") {
    return value;
  }
  return "ip_only";
}

export function describeScopeContext(
  t: TranslateFn,
  scopeTypeRaw: string | null | undefined,
  sharedAccountSuspected = false,
  historyCount?: number
): ScopeContextPresentation {
  const scopeType = normalizeReviewScopeType(scopeTypeRaw);
  const historyParams = typeof historyCount === "number" ? { count: historyCount } : undefined;

  if (scopeType === "ip_device") {
    return {
      scopeType,
      decisionTarget: t("common.scopeLabels.ipDeviceScope"),
      contextLabel: t("common.scopeLabels.deviceField"),
      contextValue: t("common.notAvailable"),
      historyTitle: t("common.scopeLabels.ipDeviceHistoryTitle"),
      historyLabel: t("common.scopeLabels.ipDeviceHistory", historyParams),
      scopeMeta: t("common.scopeLabels.ipDeviceScope")
    };
  }

  if (scopeType === "subject_ip") {
    const contextValue = sharedAccountSuspected
      ? t("common.scopeLabels.sharedAccountContext")
      : t("common.scopeLabels.subjectContext");
    return {
      scopeType,
      decisionTarget: t("common.scopeLabels.subjectIpScope"),
      contextLabel: t("common.scopeLabels.accountField"),
      contextValue,
      historyTitle: t("common.scopeLabels.subjectIpHistoryTitle"),
      historyLabel: t("common.scopeLabels.subjectIpHistory", historyParams),
      scopeMeta: contextValue
    };
  }

  return {
    scopeType,
    decisionTarget: t("common.scopeLabels.ipOnlyScope"),
    contextLabel: t("common.scopeLabels.contextField"),
    contextValue: t("common.scopeLabels.ipOnlyContext"),
    historyTitle: t("common.scopeLabels.ipOnlyHistoryTitle"),
    historyLabel: t("common.scopeLabels.ipOnlyHistory", historyParams),
    scopeMeta: t("common.scopeLabels.ipOnlyScope")
  };
}
