function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function formatDisplayDateTime(
  value: string | null | undefined,
  emptyFallback = "N/A"
): string {
  if (!value) {
    return emptyFallback;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return `${pad(parsed.getDate())}.${pad(parsed.getMonth() + 1)} ${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}
