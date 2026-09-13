import StageGauge from "../common/StageGauge.jsx";
import SourceBadge from "../common/SourceBadge.jsx";
import CaveatNote from "../common/CaveatNote.jsx";
import ManualRefCite from "../common/ManualRefCite.jsx";

const ALERT_STAGES = [
  { key: "관심", label: "관심", color: "var(--alert-관심)" },
  { key: "주의", label: "주의", color: "var(--alert-주의)" },
  { key: "경계", label: "경계", color: "var(--alert-경계)" },
  { key: "심각", label: "심각", color: "var(--alert-심각)" },
];
const ALERT_COLOR = {
  관심: "var(--alert-관심)",
  주의: "var(--alert-주의)",
  경계: "var(--alert-경계)",
  심각: "var(--alert-심각)",
};

export default function SignalStatusPanel({ envelope, forecastEnvelope }) {
  const d = envelope.data;
  const todayForecast = forecastEnvelope?.data?.daily?.[0];

  return (
    <div>
      <StageGauge stages={ALERT_STAGES} currentKey={d.alert_level} />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <span className="alert-badge" style={{ background: ALERT_COLOR[d.alert_level] }}>
          {d.alert_level}
        </span>
        {d.previous_alert_level && d.previous_alert_level !== d.alert_level && (
          <span style={{ color: "var(--ink-soft)", fontSize: 13 }}>
            ({d.previous_alert_level} → {d.alert_level})
          </span>
        )}
        <span style={{ fontSize: 12, color: "var(--ink-soft)", fontFamily: "var(--font-mono)" }}>
          기준일 {d.as_of}
        </span>
      </div>

      <div style={{ display: "flex", gap: 24, marginBottom: 12, fontSize: 14 }}>
        <div>
          혼잡도 단계 <strong>{d.congestion_level}</strong> / 5
        </div>
        <div>
          밀도 <strong>{d.density.value}</strong> {d.density.unit}
          {d.density.slope_corrected ? " (경사 보정됨)" : ""}
        </div>
      </div>

      <p style={{ fontSize: 14 }}>{d.basis}</p>

      <ManualRefCite manualRef={d.manual_ref} />

      {todayForecast && (
        <div className="info-box">
          오늘({todayForecast.date}) 예측 방문객 <strong>{todayForecast.predicted.toLocaleString()}</strong>명
          · 예상 경보 <strong>{todayForecast.expected_alert_level}</strong>
          <span style={{ color: "var(--ink-soft)" }}> — 90일 전체 예측은 AREA 1에서 확인</span>
        </div>
      )}

      <SourceBadge envelope={envelope} />
      <CaveatNote envelope={envelope} />
    </div>
  );
}
