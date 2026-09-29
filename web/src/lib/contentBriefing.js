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
  const recentVideos = items.filter((item) => item.published_at >= daysBefore(end, 6));

  return { end, recentVideos };
}
