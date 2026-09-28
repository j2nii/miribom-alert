import { alignedSignalSeries } from "./alignedSignalSeries.js";

const DAY = 86400000;

function consecutive(rows) {
  return rows.every((row, index) => index === 0
    || Date.parse(`${row.date}T00:00:00Z`) - Date.parse(`${rows[index - 1].date}T00:00:00Z`) === DAY);
}

export function summarizeVisitorSignal(seriesData) {
  const { daily } = alignedSignalSeries(seriesData);
  const valid = daily.filter((row) => Number.isFinite(row.visitors));
  const latest = valid.at(-1) ?? null;
  const threshold = seriesData?.thresholds?.visitors;
  const duration = seriesData?.thresholds?.min_duration ?? 7;
  const signalWindow = valid.slice(-duration);
  const detected = Number.isFinite(threshold) && signalWindow.length === duration && consecutive(signalWindow)
    && signalWindow.every((row) => Number.isFinite(row.visitors_stat) && row.visitors_stat > threshold);
  const lastFourteen = valid.slice(-14);
  const comparable = lastFourteen.length === 14 && consecutive(lastFourteen);
  const currentTotal = comparable ? lastFourteen.slice(-7).reduce((sum, row) => sum + row.visitors, 0) : null;
  const previousTotal = comparable ? lastFourteen.slice(0, 7).reduce((sum, row) => sum + row.visitors, 0) : null;
  const weekChange = previousTotal > 0 ? (currentTotal / previousTotal - 1) * 100 : null;
  return { latest, detected: Number.isFinite(threshold) ? detected : null, weekChange, threshold, duration };
}
