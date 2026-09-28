import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import SignalTrendChart from "../components/trend/SignalTrendChart.jsx";
import PointVsTotalChart from "../components/trend/PointVsTotalChart.jsx";
import { useState } from "react";
import ForecastChart from "../components/trend/ForecastChart.jsx";
import OutlookChart from "../components/trend/OutlookChart.jsx";
import { fmtMD, fmtYM, fix } from "../components/common/chart/chartKit.js";
import "../components/trend/trend.css";

// 신호 추이·예측 (AREA 0 바로 아래, 전체 폭). 9/26 회의: "스파이크가 실제로 튀는 걸 잘 보이는 위치에".
// ① 검색·방문이 실제로 어떻게 움직였나 ② 그 움직임이 어느 지점에서 났나 ③ 앞으로 7일은 어떤가
export default function SignalTrend({ region }) {
  const series = useRegionData("signal_series", region);
  const forecast = useRegionData("forecast", region);
  const timeline = useRegionData("timeline", region);
  const outlook = useRegionData("outlook", region);
  const [tab, setTab] = useState("outlook");

  const s = series.status === "ok" ? series.envelope.data : null;
  const tl = timeline.status === "ok" ? timeline.envelope.data : null;
  const fc = forecast.status === "ok" ? forecast.envelope.data : null;
  const ol = outlook.status === "ok" ? outlook.envelope.data : null;

  return (
    <>
      <div className="panel-head">
        <p className="panel-eyebrow">SIGNAL TREND · 신호 추이와 예측</p>
        <h2>무엇이 튀었고, 어디서 났고, 앞으로는 어떤가</h2>
        <p className="panel-subtitle">
          검색·방문 신호의 실제 움직임, 관광지점과 시군구 총량의 차이, 7일 예측과 6개월 월별 전망을 한 화면에서 봅니다. 모든 값은 실측 자료이며 목업이 없습니다.
          전망은 행사 기획·예산 편성 참고용이고, 어떻게 계산했는지는 '근거 보기'에서 확인할 수 있습니다.
        </p>
      </div>

      {s && <SummaryTiles s={s} tl={tl} fc={fc} />}

      <div className="section-block">
        <p className="section-title">① 검색 관심과 외지인 방문 — 최근 1년</p>
        <DataState
          result={series}
          render={({ envelope }) => (
            <>
              <SignalTrendChart series={envelope.data} timeline={tl} outlook={ol} />
              <SourceBadge envelope={envelope} />
            </>
          )}
        />
      </div>

      <div className="trend-split">
        <div className="section-block">
          <p className="section-title">② 관광지점 vs 시군구 총량 — 전년 같은 달 대비</p>
          <DataState
            result={series}
            render={({ envelope }) => (
              <PointVsTotalChart points={envelope.data.points} regionName={envelope.data.region.name} outlook={ol} />
            )}
          />
        </div>

        <div className="section-block">
          <div className="section-title-row">
            <p className="section-title">③ 방문객 예측</p>
            <div className="seg-tabs" role="tablist" aria-label="예측 기간">
              {[
                ["outlook", "6개월 월별 전망"],
                ["forecast", "7일 일별 예측"],
              ].map(([key, label]) => (
                <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "is-active" : ""} onClick={() => setTab(key)}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          {tab === "outlook" ? (
            <DataState
              result={outlook}
              render={({ envelope }) => (
                <>
                  <OutlookChart outlook={envelope.data} />
                  <SourceBadge envelope={envelope} />
                  <CaveatNote envelope={envelope} />
                </>
              )}
            />
          ) : (
            <DataState
              result={forecast}
              render={({ envelope }) => (
                <>
                  <ForecastChart forecast={envelope.data} series={s} />
                  <SourceBadge envelope={envelope} />
                  <CaveatNote envelope={envelope} />
                </>
              )}
            />
          )}
        </div>
      </div>

      {series.status === "ok" && <CaveatNote envelope={series.envelope} />}
    </>
  );
}

function SummaryTiles({ s, tl, fc }) {
  const tiles = [];
  const search = s.episodes.filter((e) => e.metric === "search");
  if (search.length) {
    const top = [...search].sort((a, b) => b.peak - a.peak)[0];
    tiles.push({
      label: "검색 신호 확정",
      value: fmtMD(top.confirm),
      sub: `최고 ${fix(top.peak, 2)}배(${fmtMD(top.peak_date)}) · 임계 ${s.thresholds.search}배`,
      tone: "warn",
    });
  } else {
    tiles.push({ label: "검색 신호", value: "없음", sub: `최근 1년 임계(${s.thresholds.search}배) ${s.thresholds.min_duration}일 연속 초과 없음` });
  }

  const lead = s.points.attractions[0];
  if (lead) {
    const best = lead.series.reduce((a, b) => (b.ratio > a.ratio ? b : a));
    const total = s.points.region_total.find((r) => r.month === best.month)?.ratio;
    tiles.push({
      label: `지점 최고 배율 · ${fmtYM(best.month)}`,
      value: `${fix(best.ratio, 1)}배`,
      sub: `${lead.name} · 같은 달 ${s.region.name} ${total == null ? "자료 없음" : `${fix(total, 2)}배`}`,
      tone: best.ratio >= s.points.surge ? "accent" : undefined,
    });
  } else {
    tiles.push({ label: "지점 비교", value: "자료 없음", sub: "전년과 짝지을 지점 입장객 자료가 없음" });
  }

  const lag = tl?.lags?.signal_to_action_days;
  if (lag != null && tl.events?.some((e) => e.type === "조치 시행")) {
    tiles.push({
      label: "검색 신호 → 첫 행정 조치",
      value: lag > 0 ? `${lag}일 앞섬` : lag < 0 ? `${-lag}일 늦음` : "같은 날",
      sub: "사례 1건의 사후 확인이며 일반화한 리드타임이 아님",
    });
  } else if (fc) {
    const peak = [...fc.daily].sort((a, b) => b.predicted - a.predicted)[0];
    tiles.push({
      label: "7일 중 최대 예상",
      value: `${peak.predicted.toLocaleString("ko-KR")}명`,
      sub: `${fmtMD(peak.date)} · 80% 구간 ${peak.lower.toLocaleString("ko-KR")}~${peak.upper.toLocaleString("ko-KR")}`,
    });
  }

  return (
    <div className="summary-tiles">
      {tiles.map((t) => (
        <div key={t.label} className={`summary-tile${t.tone ? ` is-${t.tone}` : ""}`}>
          <p className="summary-tile__label">{t.label}</p>
          <p className="summary-tile__value">{t.value}</p>
          <p className="summary-tile__sub">{t.sub}</p>
        </div>
      ))}
    </div>
  );
}
