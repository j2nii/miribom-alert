import { useEffect, useState } from "react";
import Header from "./components/common/Header.jsx";
import GuideTour, { hasSeenTour } from "./components/common/GuideTour.jsx";
import ChatWidget from "./components/common/ChatWidget.jsx";
import { getManifestEntry, isRegionCode } from "./data/manifest.js";
import { normalizeRegionKey, regionLabelOf, useRegionIndex } from "./data/regionIndex.js";
import Area0Dashboard from "./pages/Area0Dashboard.jsx";
import Area1SignalScan from "./pages/Area1SignalScan.jsx";
import Area2Content from "./pages/Area2Content.jsx";
import Area3Briefing from "./pages/Area3Briefing.jsx";
import Area4Performance from "./pages/Area4Performance.jsx";
import AreaDeepAnalysis from "./pages/AreaDeepAnalysis.jsx";
import AreaPolicyReport from "./pages/AreaPolicyReport.jsx";

// The opening rows present the daily briefing. The later rows collect the
// supporting analysis and policy material in one report flow.
export default function App() {
  const [region, setRegion] = useState(() => normalizeRegionKey(new URLSearchParams(window.location.search).get("region")) ?? "yeongwol");
  const { index } = useRegionIndex();
  useEffect(() => {
    if (index && isRegionCode(region) && !index.byKey.has(region)) setRegion("yeongwol");
  }, [index, region]);
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("region") === region) return;
    url.searchParams.set("region", region);
    window.history.replaceState(null, "", url);
  }, [region]);

  const [tourOpen, setTourOpen] = useState(false);
  // 첫 방문이면 사용법 투어를 연다. 한 박자 기다리는 이유: 투어는 화면에 실제로 있는
  // 요소만 골라 잡는데, 정적 JSON이 도착하기 전에는 "오늘의 결론" 같은 단계가 아직
  // 렌더되지 않아 통째로 빠진다.
  useEffect(() => {
    if (hasSeenTour()) return undefined;
    const timer = setTimeout(() => setTourOpen(true), 900);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="app">
      <Header region={region} onRegionChange={setRegion} onReplayTour={() => setTourOpen(true)} />
      <main className="app-grid">
        <section id="area0" className="panel panel-dashboard">
          <Area0Dashboard region={region} />
        </section>

        <section id="area2" className="panel panel-summary panel-scroll">
          <Area2Content region={region} />
        </section>

        <section id="area3" className="panel panel-briefing">
          <Area3Briefing region={region} />
        </section>

        <div id="area1" className="analysis-report-intro">
          <h2>심층 분석 보고서</h2>
          <p>브리핑의 판단 근거를 방문 흐름, 지역 구성, 콘텐츠와 정책 대응 순서로 확인합니다.</p>
          <nav aria-label="심층 분석 보고서 목차">
            <a href="#visit-analysis">방문 흐름·예측</a>
            <a href="#signal-evidence">신호 판정 근거</a>
            {getManifestEntry(region, "content_type") && <a href="#content-analysis">콘텐츠 유형</a>}
            {getManifestEntry(region, "checklist") && <a href="#policy-report">대응 체크리스트</a>}
          </nav>
        </div>

        <section id="visit-analysis" className="panel panel-scan panel-scroll">
          <Area1SignalScan region={region} />
        </section>

        <section className="panel panel-evidence">
          <AreaDeepAnalysis region={region} />
        </section>

        <section id="policy-report" className="panel panel-policy-report">
          <AreaPolicyReport region={region} />
        </section>

        <section id="area4" className="panel panel-performance">
          <Area4Performance region={region} />
        </section>
      </main>
      <ChatWidget key={region} region={region} regionLabel={regionLabelOf(region, index)} />
      <GuideTour open={tourOpen} onClose={() => setTourOpen(false)} />
    </div>
  );
}
