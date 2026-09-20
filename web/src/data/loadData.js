import { getManifestEntry } from "./manifest.js";

/**
 * Fetches one data-contract file (the "envelope": _mock/source/period/
 * caveat/data) for a region. Never returns raw hardcoded literals -- every
 * component in this app must go through this function.
 *
 * @param {string} dataType - one of the 9 schema names, e.g. "signal_status"
 * @param {{ region: string }} opts
 * @returns {Promise<
 *   | { status: "unsupported", region: string, dataType: string }
 *   | { status: "error", region: string, dataType: string, error: string }
 *   | { status: "ok", region: string, dataType: string, kind: string, envelope: object }
 * >}
 */
export async function loadData(dataType, { region }) {
  const entry = getManifestEntry(region, dataType);
  if (!entry) {
    return { status: "unsupported", region, dataType };
  }

  try {
    const res = await fetch(entry.url);
    if (!res.ok) {
      return { status: "error", region, dataType, error: `HTTP ${res.status}` };
    }
    const envelope = await res.json();
    return { status: "ok", region, dataType, kind: entry.kind, envelope };
  } catch (err) {
    return { status: "error", region, dataType, error: String(err) };
  }
}
