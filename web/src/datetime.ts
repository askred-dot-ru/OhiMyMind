/** Project-wide date/time for lists and cards. Time never includes seconds. */

function startOfLocalDay(value: Date): number {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
}

function formatTime(value: Date): string {
  return value.toLocaleTimeString("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatCalendarDate(value: Date, now: Date): string {
  const sameYear = value.getFullYear() === now.getFullYear();
  const text = value.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
    ...(sameYear ? {} : { year: "numeric" }),
  });
  return text.replace(/\sг\.?/g, "").replace(/\s+/g, " ").trim();
}

export function formatWhen(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return "";
  const value = new Date(iso);
  if (Number.isNaN(value.getTime())) return iso;
  const time = formatTime(value);
  const diffDays = Math.round((startOfLocalDay(now) - startOfLocalDay(value)) / 86_400_000);
  if (diffDays === 0) return `сегодня ${time}`;
  if (diffDays === 1) return `вчера ${time}`;
  if (diffDays === 2) return `позавчера ${time}`;
  return `${formatCalendarDate(value, now)} ${time}`;
}
