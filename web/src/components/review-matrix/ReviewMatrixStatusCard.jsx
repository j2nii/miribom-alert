import { useEffect, useMemo, useState } from "react";
import { findReviewMatrixRegion, loadReviewMatrix } from "../../data/loadReviewMatrix.js";
import "./review-matrix.css";
import { reviewMatrixPresentation } from "./presentation.js";

const STATE_CLASS = {
  normal: "matrix-state--normal",
  online_watch: "matrix-state--online",
  demand_anomaly: "matrix-state--demand",
  combined_alert: "matrix-state--combined",
};

export default function ReviewMatrixStatusCard({ regionId }) {
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    loadReviewMatrix()
      .then((value) => active && setPayload(value))
      .catch((reason) => active && setError(reason.message));
    return () => {
      active = false;
    };
  }, []);

  const region = useMemo(
    () => (payload ? findReviewMatrixRegion(payload, regionId) : null),
    [payload, regionId],
  );

  if (error) return <section className="matrix-card matrix-card--error">{error}</section>;
  if (!payload) return <section className="matrix-card">최신 검토 상태를 불러오는 중입니다.</section>;
  if (!region) return <section className="matrix-card">선택한 지역의 검토 상태가 없습니다.</section>;

  const { as_of: asOf, freshness } = payload.data;
  const presentation = reviewMatrixPresentation(region.state, freshness);
  return (
    <section className="matrix-card" aria-label={`${region.region_name} 2x2 검토 상태`}>
      <header className="matrix-card__header">
        <div>
          <p className="matrix-card__eyebrow">{presentation.freshnessLabel}</p>
          <h3>{region.region_name} 검토 상태</h3>
        </div>
        <span className={`matrix-state ${STATE_CLASS[region.state] ?? "matrix-state--normal"}`}>{presentation.label}</span>
      </header>

      {freshness?.stale && (
        <p className="matrix-card__stale">
          수집 지연 · 판정 기준 {asOf.decision}. 오늘의 실시간 상태가 아닙니다.
        </p>
      )}

      <div className="matrix-signals">
        <div>
          <span>온라인 관심</span>
          <strong>{region.search_watch_active ? "관심 후보 포착" : "후보 미선정"}</strong>
          <small>검색 기준 {asOf.search}</small>
        </div>
        <div>
          <span>현장 수요</span>
          <strong>{region.visitor_anomaly_active ? "수요 이상 포착" : "이상 미포착"}</strong>
          <small>방문 기준 {asOf.visitor}</small>
        </div>
      </div>

      <p className="matrix-card__interpretation">{presentation.interpretation}</p>
      <div className="matrix-card__action">
        <span>권고</span>
        <strong>{region.recommended_action}</strong>
      </div>
      <p className="matrix-card__note">판정 기준 {asOf.decision} · 담당자 검토 우선순위입니다. 설명용 예시는 이 판정에 사용하지 않습니다.</p>
    </section>
  );
}
