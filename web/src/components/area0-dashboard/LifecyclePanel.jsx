import StageGauge from "../common/StageGauge.jsx";
import ConfidenceBox from "../common/ConfidenceBox.jsx";
import TrendChart from "../common/TrendChart.jsx";
import SourceBadge from "../common/SourceBadge.jsx";
import CaveatNote from "../common/CaveatNote.jsx";

const LIFECYCLE_STAGES = [
  { key: "발화", label: "발화", color: "var(--slate)" },
  { key: "확산", label: "확산", color: "var(--amber)" },
  { key: "피크", label: "피크", color: "var(--crimson)" },
  { key: "쇠퇴", label: "쇠퇴", color: "var(--teal)" },
];

// Dedicated widget for schema-independent "lifecycle reference" regions
// (currently only 충주) -- a distinct data shape from Geoje's alert_level
// schema (lifecycle_stage/lifecycle_series/thresholds/confidence instead of
// alert_level/cross_validation), so it gets its own gauge + confidence box +
// trend chart rather than being forced through SignalStatusPanel.
export default function LifecyclePanel({ envelope }) {
  const d = envelope.data;
  const series = d.lifecycle_series;

  // Month-over-month % change, plotted (not raw mention counts) so the
  // decline threshold reads as one flat dashed line throughout.
  const changes = series.slice(1).map((cur, i) => {
    const prev = series[i];
    const pct = Math.round(((cur.mentions - prev.mentions) / prev.mentions) * 1000) / 10;
    return { month: cur.month.slice(2).replace("-", "."), pct, stage: cur.stage, mentions: cur.mentions };
  });

  const latest = changes[changes.length - 1];
  const { spread_pct, decline_pct } = d.thresholds;
  const line =
    latest.pct <= decline_pct
      ? `SNS 언급량 추세 최근 1개월 대비 언급량이 ${latest.pct}% 줄어 쇠퇴 기준(${decline_pct}% 이하)에 해당합니다.`
      : latest.pct >= spread_pct
      ? `SNS 언급량 추세 최근 1개월 대비 언급량이 +${latest.pct}% 늘어 확산 기준(${spread_pct}% 이상)에 해당합니다.`
      : `SNS 언급량 추세 최근 1개월 대비 언급량 변화(${latest.pct}%)가 확산·쇠퇴 기준 사이에 있어 뚜렷한 신호가 아닙니다.`;

  return (
    <div>
      {/* SignalStatusPanel과 같은 클래스 -- 사용법 투어가 지역 스키마와 무관하게 같은
          "지금 상태" 영역을 비출 수 있게 한다. */}
      <div className="alert-summary">
        <StageGauge stages={LIFECYCLE_STAGES} currentKey={d.lifecycle_stage} />
      </div>

      <ConfidenceBox
        matchedCount={d.confidence.matched_count}
        totalCount={d.confidence.total_count}
        lines={[line]}
        note={d.confidence.note}
      />

      <TrendChart
        points={changes}
        valueKey="pct"
        labelKey="month"
        thresholdValue={decline_pct}
        thresholdLabel={`쇠퇴 기준 (${decline_pct}%)`}
        isResolvedFn={(p) => p.pct <= decline_pct}
        tooltipFn={(p) => `${p.month}: 전월 대비 ${p.pct}% (${p.stage}, 언급량 ${p.mentions.toLocaleString()}건)`}
      />

      <div className="info-box" style={{ marginTop: 12 }}>
        {d.narrative.text}
      </div>

      <SourceBadge envelope={envelope} />
      <CaveatNote envelope={envelope} />
    </div>
  );
}
