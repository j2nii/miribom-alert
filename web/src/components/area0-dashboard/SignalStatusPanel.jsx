import { formatDateWithWeekday } from "../../lib/format.js";
import { ALERT_STAGES, ALERT_COLOR, ALERT_MEANING } from "../../lib/alertLevels.js";
import StageGauge from "../common/StageGauge.jsx";
import SourceBadge from "../common/SourceBadge.jsx";
import CaveatNote from "../common/CaveatNote.jsx";
import ManualRefCite from "../common/ManualRefCite.jsx";

export default function SignalStatusPanel({ envelope, forecastEnvelope }) {
  const d = envelope.data;
  const todayForecast = forecastEnvelope?.data?.daily?.[0];

  return (
    <div>
      {/* 게이지 + 단계 배지 + 기준일 + 단계의 뜻을 한 덩어리로 묶는다. 사용법 투어가 이
          영역을 통째로 비추기 때문에(GuideTour의 .alert-summary 단계), 바늘만 밖에 남거나
          설명만 비춰지는 일이 없어야 한다. */}
      <div className="alert-summary">
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
          기준일 {formatDateWithWeekday(d.as_of)}
        </span>
      </div>

      {/* 단계 이름만으로는 무엇을 해야 하는지 알 수 없다 -- 단계의 뜻을 게이지 바로 밑에 붙인다. */}
      {ALERT_MEANING[d.alert_level] && (
        <p className="alert-meaning">{ALERT_MEANING[d.alert_level]}</p>
      )}
      </div>

      {/* agents 브랜치 계약 변경: congestion_level·density는 실데이터에서 둘 다
          없을 수 있다 (혼잡도 미측정 지역/시점 등). congestion_level의
          스키마 주석은 "화면은 '미측정'으로 표시"라고 명시하므로 숨기지
          않고 그대로 드러낸다 -- density는 그런 지시가 없어 있을 때만 표시. */}
      <div style={{ display: "flex", gap: 24, marginBottom: 12, fontSize: 14, flexWrap: "wrap" }}>
        <div>
          혼잡도 단계 <strong>{d.congestion_level != null ? `${d.congestion_level} / 5` : "미측정"}</strong>
        </div>
        {d.density && (
          <div>
            밀도 <strong>{d.density.value}</strong> {d.density.unit}
            {d.density.slope_corrected ? " (경사 보정됨)" : ""}
          </div>
        )}
      </div>

      <p style={{ fontSize: 14 }}>{d.basis}</p>

      <ManualRefCite manualRef={d.manual_ref} />

      {todayForecast && (
        <div className="info-box">
          오늘({formatDateWithWeekday(todayForecast.date)}) 예측 방문객 <strong>{todayForecast.predicted.toLocaleString()}</strong>명
          · 예상 경보 <strong>{todayForecast.expected_alert_level}</strong>
          <span style={{ color: "var(--ink-soft)" }}> — 90일 전체 예측은 AREA 1에서 확인</span>
        </div>
      )}

      <SourceBadge envelope={envelope} />
      <CaveatNote envelope={envelope} />
    </div>
  );
}
