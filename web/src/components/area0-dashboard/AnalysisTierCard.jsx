import { useRegionIndex } from "../../data/regionIndex.js";
import { BASIC_FEATURES, CASE_NAMES, CASE_REGIONS, deepCoverage } from "../../data/analysisTiers.js";
import "./tierCard.css";

// 받침이 있으면 "은", 없으면 "는" (영월군은 · 포항시는)
function eunNeun(word) {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  return code >= 0 && code <= 11171 && code % 28 !== 0 ? "은" : "는";
}

// 지역 선택 바로 아래: 이 지역이 '심층 분석' 지역인지 '기본 분석' 지역인지, 무엇이 되고 무엇이
// 준비 중인지를 한 장으로 보여준다. 9/28 요청 — 사례 6곳의 심층 분석을 분명히 드러내고,
// 나머지 지역에는 심층 분석이 준비 중이라는 안내를 붙인다.
export default function AnalysisTierCard({ region, onRegionChange }) {
  const { index } = useRegionIndex();
  const entry = index?.byKey.get(region);
  if (!entry) return null; // 사전 로딩 전, 또는 충주 샘플처럼 사전 밖 지역

  const deep = deepCoverage(entry);
  const isCase = Boolean(entry.case);

  return (
    <section className={`tier-card${isCase ? " tier-card--deep" : ""}`} aria-label="이 지역의 분석 범위">
      <div className="tier-card__head">
        <span className={`tier-card__badge${isCase ? " is-deep" : ""}`}>{isCase ? "심층 분석 지역" : "기본 분석 지역"}</span>
        <p className="tier-card__title">
          {isCase ? (
            <>
              <b>{entry.name}</b>
              {eunNeun(entry.name)} 공개 데이터에 <b>유튜브·기사 수집 자료와 AI 에이전트 분석</b>까지 연결된 사례 지역입니다
            </>
          ) : (
            <>
              <b>{entry.label}</b>
              {eunNeun(entry.label)} <b>공개 데이터(데이터랩·이동통신·검색지수)</b>로 기본 분석을 제공합니다. 심층 분석은{" "}
              <b>준비 중</b>입니다
            </>
          )}
        </p>
      </div>

      <div className="tier-card__cols">
        <div className="tier-card__col">
          <p className="tier-card__col-title">
            기본 분석 <span>전국 226개 시군구</span>
          </p>
          <ul>
            {BASIC_FEATURES.map((f) => (
              <li key={f.type} className="is-ready">
                <i aria-hidden="true">✓</i>
                <span>
                  {f.label}
                  <small>{f.desc}</small>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="tier-card__col">
          <p className="tier-card__col-title">
            심층 분석{" "}
            <span>{isCase ? `이 지역 ${deep.ready}/${deep.total}` : `사례 ${CASE_REGIONS.length}곳에서 제공 중`}</span>
          </p>
          <ul>
            {deep.items.map((f) => (
              <li key={f.type} className={f.ready ? "is-ready" : "is-pending"}>
                <i aria-hidden="true">{f.ready ? "✓" : "…"}</i>
                <span>
                  {f.label}
                  <small>{f.ready ? f.desc : "준비 중"}</small>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="tier-card__foot">
        <span className="tier-card__foot-label">{isCase ? "다른 심층 분석 지역" : "지금 심층 분석을 볼 수 있는 곳"}</span>
        <div className="tier-card__chips">
          {CASE_REGIONS.map((c) => {
            const e = index.byKey.get(c.key);
            const cov = deepCoverage(e);
            const current = c.key === region;
            return (
              <button
                key={c.key}
                type="button"
                className={`tier-chip${current ? " is-current" : ""}`}
                onClick={() => !current && onRegionChange(c.key)}
                aria-current={current ? "true" : undefined}
                title={`${e?.sido_short ?? ""} ${e?.name ?? c.label} · 심층 항목 ${cov.ready}/${cov.total}`}
              >
                {c.label}
                {c.role && <small>{c.role}</small>}
              </button>
            );
          })}
        </div>
        {!isCase && (
          <p className="tier-card__note">
            심층 분석은 현재 {CASE_NAMES} 6곳에서 제공하며, 다른 시군구로 순차 확대를 준비하고 있습니다. 기본 분석은 공개 데이터만 쓰므로 지금 바로 전국 어디서나 동작합니다.
          </p>
        )}
      </div>
    </section>
  );
}
