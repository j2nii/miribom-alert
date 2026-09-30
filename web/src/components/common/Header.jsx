import { useEffect, useState } from "react";
import RegionSearchPicker from "./RegionSearchPicker.jsx";

const STEPS = [
  { label: "현황 확인", note: "지역의 경보 상태", icon: "M4 18V10m5 8V6m5 12v-5m5 5V3" },
  { label: "신호 탐색", note: "변화를 먼저 발견", icon: "M3 12h4l3-7 4 14 3-7h4" },
  { label: "원인 분석", note: "콘텐츠와 방문 흐름", icon: "M10 17a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm5-2 6 6" },
  { label: "대응 준비", note: "체크리스트와 브리핑", icon: "M8 4h12v17H4V4h4m0-2h8v5H8V2Zm0 10 2 2 5-5m-7 9h8" },
  { label: "성과 확인", note: "대응 이후의 변화", icon: "M4 3v17h17M7 15l4-4 4 2 5-7m-5 0h5v5" },
];

const NAV_ITEMS = [
  { href: "#area0", label: "이슈 브리핑", icon: STEPS[0].icon },
  { href: "#area2", label: "관련 콘텐츠", icon: STEPS[2].icon },
  { href: "#area3", label: "대응 준비", icon: STEPS[3].icon },
  { href: "#area1", label: "심층 분석", icon: STEPS[1].icon },
  { href: "#area4", label: "대응 기록", icon: STEPS[4].icon },
];

export default function Header({ region, onRegionChange, onReplayTour }) {
  const [selectedRegion, setSelectedRegion] = useState(region);
  useEffect(() => setSelectedRegion(region), [region]);

  function showRegion(event) {
    event.preventDefault();
    onRegionChange(selectedRegion);
    window.location.hash = "area0";
    document.getElementById("area0")?.scrollIntoView({ block: "start" });
  }

  return (
    <>
      <a className="skip-link" href="#area0">지역 현황 바로가기</a>
      <div className="portal-utility"><div className="portal-width"><span>지역 관광 데이터 브리핑</span></div></div>
      <header className="app-header">
        <div className="portal-width portal-header-row">
          <a className="portal-brand" href="#" aria-label="미리봄 홈">
            <svg className="brand-radar" viewBox="0 0 48 48" fill="none" aria-hidden="true">
              <circle cx="24" cy="24" r="20" fill="currentColor" fillOpacity=".05" stroke="currentColor" strokeWidth="1.8" />
              <circle cx="24" cy="24" r="13" stroke="currentColor" strokeOpacity=".35" strokeWidth="1.2" />
              <circle cx="24" cy="24" r="6" stroke="currentColor" strokeOpacity=".35" strokeWidth="1.2" />
              <path d="M24 4V44M4 24H44" stroke="currentColor" strokeOpacity=".25" />
              <path d="M24 24V4A20 20 0 0 1 41.32 14Z" fill="currentColor" fillOpacity=".18" />
              <path d="M24 24L41.32 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <circle cx="24" cy="24" r="2.5" fill="currentColor" />
              <circle cx="33" cy="16" r="3.2" fill="currentColor" stroke="white" strokeWidth="1.2" />
              <circle cx="14" cy="32" r="2.4" fill="currentColor" fillOpacity=".65" stroke="white" strokeWidth="1" />
            </svg>
            미리<span>봄</span>
          </a>
          <form className="header-region-picker" onSubmit={showRegion}>
            <label htmlFor="active-region">관심 지역 선택</label>
            <RegionSearchPicker selected={selectedRegion} current={region} onSelect={setSelectedRegion} />
            <button type="submit">현황 보기 <span aria-hidden="true">→</span></button>
          </form>
          {/* 투어 재생 버튼은 form 밖에 둔다 -- 안에 두면 .header-region-picker button
              규칙이 잡아 "현황 보기" submit 버튼과 생김새가 같아진다. */}
          <button type="button" className="header-tour-replay" onClick={onReplayTour}>사용법 보기</button>
        </div>
      </header>
      <nav className="portal-navigation" aria-label="서비스 메뉴">
        <div className="portal-width">
          <div className="workflow-nav">
            {NAV_ITEMS.map((item, i) => {
              return <a className="workflow-step" key={item.href} href={item.href}>
                <span className="workflow-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={item.icon} /></svg></span>
                <span className="workflow-label"><small>0{i + 1}</small>{item.label}</span>
              </a>
            })}
          </div>
        </div>
      </nav>
      <section className="portal-hero" aria-labelledby="service-title">
        <div className="portal-width hero-inner">
          <div className="hero-copy">
            <h1 id="service-title">우리 지역 관광 변화, 한눈에</h1>
            <p className="hero-description">검색 흐름부터 외지인 방문과 대응 준비까지 이어서 확인하세요.</p>
          </div>
        </div>
      </section>
    </>
  );
}
