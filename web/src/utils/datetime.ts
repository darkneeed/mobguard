import type { Language } from "../localization";

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatCompactDuration(
  totalSeconds: number | null | undefined,
  emptyFallback = "N/A",
  language: Language = "ru"
): string {
  if (totalSeconds === null || totalSeconds === undefined || Number.isNaN(totalSeconds)) {
    return emptyFallback;
  }

  const safeSeconds = Math.max(Math.floor(totalSeconds), 0);
  const labels =
    language === "en"
      ? { day: "d", hour: "h", minute: "m", second: "s", zero: "0m" }
      : { day: "д", hour: "ч", minute: "м", second: "с", zero: "0м" };

  if (safeSeconds === 0) {
    return labels.zero;
  }

  const days = Math.floor(safeSeconds / 86400);
  const hours = Math.floor((safeSeconds % 86400) / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const seconds = safeSeconds % 60;
  const chunks: string[] = [];

  if (days > 0) chunks.push(`${days}${labels.day}`);
  if (hours > 0) chunks.push(`${hours}${labels.hour}`);
  if (minutes > 0) chunks.push(`${minutes}${labels.minute}`);
  if (chunks.length === 0 && seconds > 0) {
    chunks.push(`${seconds}${labels.second}`);
  }

  return chunks.slice(0, 3).join(" ") || labels.zero;
}

export function formatObservedDuration(
  startedAt: string | null | undefined,
  endedAt: string | null | undefined,
  emptyFallback = "N/A",
  language: Language = "ru"
): string {
  const started = parseDate(startedAt);
  const ended = parseDate(endedAt);

  if (!started || !ended) {
    return emptyFallback;
  }

  const diffSeconds = Math.max((ended.getTime() - started.getTime()) / 1000, 0);
  return formatCompactDuration(diffSeconds, emptyFallback, language);
}

export function formatDisplayDateTime(
  value: string | null | undefined,
  emptyFallback = "N/A",
  language: Language = "ru"
): string {
  if (!value) {
    return emptyFallback;
  }

  const parsed = parseDate(value);
  if (!parsed) {
    return value;
  }

  const day = pad(parsed.getDate());
  const month = pad(parsed.getMonth() + 1);
  const time = `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;

  if (language === "en") {
    return `${day}/${month} ${time}`;
  }

  return `${day}.${month} ${time}`;
}
