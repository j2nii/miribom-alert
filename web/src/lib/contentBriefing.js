import { contentRelevance } from "./contentRelevance.js";

function daysBefore(date, days) {
  const value = new Date(`${date}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() - days);
  return value.toISOString().slice(0, 10);
}

export function buildContentBriefing(envelope) {
  const end = envelope?.period?.end;
  const regionName = envelope?.data?.region?.name ?? "";
  if (!end || !Array.isArray(envelope?.data?.items)) return null;

  const items = envelope.data.items
    .filter((item) => item.published_at <= end && contentRelevance(item, regionName).confirmed)
    .sort((a, b) => b.published_at.localeCompare(a.published_at) || (b.view_count ?? 0) - (a.view_count ?? 0));
  const today = items.filter((item) => item.published_at === end).length;
  const previous = items.filter((item) => item.published_at === daysBefore(end, 1)).length;
  const previousSeven = items.filter((item) => item.published_at >= daysBefore(end, 7) && item.published_at < end).length;

  const groups = new Map();
  for (const item of items) {
    const key = item.content_type || "기타";
    if (!groups.has(key)) groups.set(key, { name: key, items: [], latest: item.published_at });
    groups.get(key).items.push(item);
  }
  const topics = [...groups.values()]
    .sort((a, b) => b.latest.localeCompare(a.latest) || b.items.length - a.items.length)
    .slice(0, 3);

  return { end, total: items.length, today, previous, previousAverage: previousSeven / 7, topics };
}
