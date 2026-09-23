// One-time generator for data/prod/{region}_signal_status.json.
//
// Why this is a build-time script and not a live /api/*.js route: the DB's
// vw_daily_anomaly_scored view takes 180+ seconds to answer even when
// filtered to a single region_id (it appears to compute its window-function
// baselines/z-scores across all 228 regions before the outer WHERE is
// applied). That's far past any serverless function's timeout. But the
// competition data is frozen (docs/meeting-notes/DB/관광바이럴조기경보DB사용설명서.pdf)
// and never changes, so there's no need to query it per request at all --
// run this once, commit the JSON, and treat it exactly like agent②'s
// content_type.json (data/prod/*.json, kind:"real" in the manifest).
//
// Usage: node --env-file=.env scripts/generate-signal-status.mjs
import fs from "node:fs";
import path from "node:path";
import { getPool } from "../api/_lib/db.js";
import { REFERENCE_DATE } from "../api/_lib/referenceDate.js";

const REGIONS = {
  yeongwol: { regionId: "51750", regionName: "영월군" },
  geoje: { regionId: "48310", regionName: "거제시" },
};

const LEVELS = ["관심", "주의", "경계", "심각"];
const REQUIRED_EXCEEDED = { 관심: 1, 주의: 2, 경계: 3 };

function signalCount(row) {
  return [row.is_interest_spike_current, row.is_demand_spike_current, row.is_viral_candidate].filter(
    (v) => v === 1
  ).length;
}

function countToLevel(count) {
  if (count >= 3) return "심각";
  if (count === 2) return "경계";
  if (count === 1) return "주의";
  return "관심";
}

// docs/설계결정.md D-05: 하향은 2회 연속 미달 시에만 (깜빡임 방지).
function walkAlertLevel(rowsChronological) {
  let level = "관심";
  let previousLevel = "관심";
  let downgradeStreak = 0;

  for (const row of rowsChronological) {
    const targetLevel = countToLevel(signalCount(row));
    const levelIdx = LEVELS.indexOf(level);
    const targetIdx = LEVELS.indexOf(targetLevel);

    previousLevel = level;
    if (targetIdx > levelIdx) {
      level = targetLevel;
      downgradeStreak = 0;
    } else if (targetIdx < levelIdx) {
      downgradeStreak += 1;
      if (downgradeStreak >= 2) {
        level = targetLevel;
        downgradeStreak = 0;
      }
    } else {
      downgradeStreak = 0;
    }
  }
  return { level, previousLevel };
}

function trendOf(latest, weekAgo, field) {
  if (latest?.[field] == null || weekAgo?.[field] == null) return "유지";
  const diff = latest[field] - weekAgo[field];
  if (diff > 0.1) return "상승";
  if (diff < -0.1) return "하락";
  return "유지";
}

function round(n, digits = 2) {
  return n == null ? null : Number(n.toFixed(digits));
}

async function buildEnvelope(pool, regionKey) {
  const region = REGIONS[regionKey];
  console.log(`[${regionKey}] querying vw_daily_anomaly_scored (this can take a few minutes)...`);
  const t0 = Date.now();
  const [rowsDesc] = await pool.query(
    `SELECT DATE_FORMAT(observed_date, '%Y-%m-%d') AS observed_date,
            naver_interest, visitors_external, visitors_local, visitors_foreign,
            youtube_sample_videos, youtube_sample_views,
            naver_z, visitor_z, naver_z_threshold, visitor_z_threshold,
            is_interest_spike_current, is_demand_spike_current, is_viral_candidate,
            anomaly_score
     FROM vw_daily_anomaly_scored
     WHERE region_id = ? AND observed_date <= ?
     ORDER BY observed_date DESC
     LIMIT 90`,
    [region.regionId, REFERENCE_DATE]
  );
  console.log(`[${regionKey}] done in ${Math.round((Date.now() - t0) / 1000)}s, ${rowsDesc.length} rows`);

  if (rowsDesc.length === 0) throw new Error(`no rows for ${regionKey} (region_id=${region.regionId})`);

  const rowsChron = [...rowsDesc].reverse();
  const latest = rowsDesc[0];
  const weekAgo = rowsDesc[6] ?? null;
  const { level: alert_level, previousLevel } = walkAlertLevel(rowsChron);
  const exceeded_count = signalCount(latest);

  const cross_validation = [
    {
      signal: "네이버 검색 관심지수 이상탐지(z-score)",
      provider: "tour_earlywarning DB (vw_daily_anomaly_scored)",
      value: round(latest.naver_z),
      threshold: round(Number(latest.naver_z_threshold)),
      unit: "z",
      exceeded: latest.is_interest_spike_current === 1,
      trend: trendOf(latest, weekAgo, "naver_z"),
    },
    {
      signal: "외지인 방문자수 이상탐지(z-score)",
      provider: "tour_earlywarning DB (vw_daily_anomaly_scored)",
      value: round(latest.visitor_z),
      threshold: round(Number(latest.visitor_z_threshold)),
      unit: "z",
      exceeded: latest.is_demand_spike_current === 1,
      trend: trendOf(latest, weekAgo, "visitor_z"),
    },
    {
      signal: "검색·방문 결합 바이럴 후보 판정",
      provider: "tour_earlywarning DB (vw_daily_anomaly_scored)",
      value: null,
      threshold: null,
      unit: "",
      missing_reason: "네이버·방문자 신호의 결합 판정 플래그로, 별도 실측값이 없음",
      exceeded: latest.is_viral_candidate === 1,
      trend: "유지",
    },
  ];

  const levelIdx = LEVELS.indexOf(alert_level);
  const escalation =
    alert_level === "심각"
      ? { next_level: "심각", required_exceeded: 3, current_exceeded: exceeded_count, met: false, note: "이미 최고 단계입니다." }
      : {
          next_level: LEVELS[levelIdx + 1],
          required_exceeded: REQUIRED_EXCEEDED[alert_level],
          current_exceeded: exceeded_count,
          met: exceeded_count >= REQUIRED_EXCEEDED[alert_level],
        };

  const retrieved_at = new Date().toISOString().slice(0, 10);

  return {
    _mock: false,
    generated_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    source: [
      {
        name: "네이버 검색 관심지수·외지인 방문자수 이상탐지",
        provider: "tour_earlywarning DB (vw_daily_anomaly_scored, 1회 추출·정적 반영)",
        retrieved_at,
        note: "naver_interest는 상대지수(재정규화)이며 절대 검색건수가 아님. DB가 동결되어 있어 1회 추출한 값을 정적 파일로 고정함(scripts/generate-signal-status.mjs).",
      },
    ],
    period: {
      start: rowsChron[0].observed_date,
      end: latest.observed_date,
      granularity: "일",
    },
    caveat: [
      "naver_interest는 절대 검색건수가 아니라 재정규화된 상대 지수입니다 — 동일 지역의 시간 변화로 해석합니다.",
      "혼잡도 단계(congestion_level)는 실측 센서 데이터가 없어 제공하지 않습니다(미측정).",
      "화면의 기준일은 실제 오늘이 아니라 DB에 적재된 데이터의 동결 기준시점(2026-08-14)입니다.",
      "바이럴 후보 판정은 검색·방문 신호의 결합 지표로, 독립된 실측값이 없습니다.",
      "이 파일은 DB에서 1회 추출해 고정한 정적 스냅샷입니다 — DB가 갱신돼도 자동 반영되지 않으며, 재생성하려면 이 스크립트를 다시 실행해야 합니다.",
    ],
    data: {
      region: { code: region.regionId, name: region.regionName },
      as_of: latest.observed_date,
      alert_level,
      previous_alert_level: previousLevel,
      congestion_level: null,
      cross_validation,
      agreement: { exceeded_count, total: 3 },
      escalation,
      basis: `독립 신호 3개 중 ${exceeded_count}개가 임계를 초과하여 경보 단계는 ${alert_level}입니다 (검색 관심지수 ${cross_validation[0].exceeded ? "초과" : "미달"}, 방문자수 ${cross_validation[1].exceeded ? "초과" : "미달"}, 결합 바이럴 판정 ${cross_validation[2].exceeded ? "초과" : "미달"}).`,
    },
  };
}

async function main() {
  const pool = getPool();
  const outDir = path.resolve(import.meta.dirname, "../../data/prod");
  fs.mkdirSync(outDir, { recursive: true });

  for (const regionKey of Object.keys(REGIONS)) {
    const envelope = await buildEnvelope(pool, regionKey);
    const outPath = path.join(outDir, `${regionKey}_signal_status.json`);
    fs.writeFileSync(outPath, JSON.stringify(envelope, null, 2) + "\n", "utf8");
    console.log(`[${regionKey}] wrote ${outPath} (alert_level=${envelope.data.alert_level})`);
  }

  await pool.end();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
