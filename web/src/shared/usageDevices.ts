type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

function cleanText(value: unknown): string {
  return String(value ?? "").trim();
}

function deviceLabel(device: Record<string, unknown>): string {
  const label = cleanText(device.label);
  if (label) return label;
  const osFamily = cleanText(device.os_family);
  const appName = cleanText(device.app_name);
  if (osFamily && appName) {
    return `${osFamily} / ${appName}`;
  }
  if (osFamily) return osFamily;
  if (appName) return appName;
  return cleanText(device.device_id);
}

function sourceLabel(source: unknown, t: TranslateFn): string {
  const normalized = cleanText(source);
  if (normalized === "panel_user") {
    return t("common.deviceSources.panelUser");
  }
  if (normalized === "event") {
    return t("common.deviceSources.event");
  }
  return "";
}

function fallbackDeviceLabels(fallbackLabels: unknown): string[] {
  if (!Array.isArray(fallbackLabels)) {
    return [];
  }
  return fallbackLabels
    .map((item) => cleanText(item))
    .filter((item) => item.length > 0);
}

export function usageDevicePrimaryLabel(devices: unknown, fallbackLabels: unknown): string {
  if (Array.isArray(devices)) {
    for (const item of devices) {
      if (!item || typeof item !== "object") continue;
      const label = deviceLabel(item as Record<string, unknown>);
      if (label) {
        return label;
      }
    }
  }
  return fallbackDeviceLabels(fallbackLabels)[0] || "";
}

export function formatUsageDeviceInventory(
  devices: unknown,
  fallbackLabels: unknown,
  t: TranslateFn,
): string {
  if (Array.isArray(devices)) {
    const items = devices
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const typedItem = item as Record<string, unknown>;
        const label = deviceLabel(typedItem);
        if (!label) return "";
        const source = sourceLabel(typedItem.source, t);
        return source ? `${label} (${source})` : label;
      })
      .filter((item) => item.length > 0);
    const deduped = Array.from(new Set(items));
    if (deduped.length > 0) {
      return deduped.join(", ");
    }
  }
  const fallback = fallbackDeviceLabels(fallbackLabels);
  return fallback.length > 0 ? fallback.join(", ") : t("common.notAvailable");
}

export function hasPanelUsageDevices(devices: unknown): boolean {
  return Array.isArray(devices)
    && devices.some(
      (item) => item && typeof item === "object" && cleanText((item as Record<string, unknown>).source) === "panel_user",
    );
}
