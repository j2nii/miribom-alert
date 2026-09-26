import { useState } from "react";
import { REGIONS } from "./data/manifest.js";
import Header from "./components/common/Header.jsx";
import Area0Dashboard from "./pages/Area0Dashboard.jsx";
import SignalTrend from "./pages/SignalTrend.jsx";
import Area1SignalScan from "./pages/Area1SignalScan.jsx";
import Area2Content from "./pages/Area2Content.jsx";
import Area3Briefing from "./pages/Area3Briefing.jsx";
import Area4Performance from "./pages/Area4Performance.jsx";

// Layout mirrors docs/meeting-notes/tourism-radar-demo.html's own
// grid-template-areas ("scan summary" / "briefing briefing") -- AREA 0 and
// AREA 4 are bolted on as full-width rows above/below since the original
// demo predates them (it only had AREA 1-3). Each grid area renders as
// exactly one .panel, same as the reference demo (not one panel per
// sub-feature).
export default function App() {
  // ?region=geoje 처럼 지역을 주소에 실어 공유·시연 링크로 쓸 수 있다. 없거나 모르는 값이면 영월
  const [region, setRegion] = useState(() => {
    const asked = new URLSearchParams(window.location.search).get("region");
    return REGIONS.some((r) => r.key === asked) ? asked : "yeongwol";
  });

  return (
    <div className="app">
      <Header />
      <div className="app-grid">
        <section id="area0" className="panel panel-dashboard">
          <Area0Dashboard region={region} onRegionChange={setRegion} />
        </section>

        <section id="trend" className="panel panel-trend">
          <SignalTrend region={region} />
        </section>

        <section id="area1" className="panel panel-scan panel-scroll">
          <Area1SignalScan region={region} />
        </section>

        <section id="area2" className="panel panel-summary panel-scroll">
          <Area2Content region={region} />
        </section>

        <section id="area3" className="panel panel-briefing">
          <Area3Briefing region={region} />
        </section>

        <section id="area4" className="panel panel-performance">
          <Area4Performance region={region} />
        </section>
      </div>
      <footer className="app-footer">
        이 화면은 목업/실데이터가 혼재된 데모입니다. 거제시는 9종 데이터 스키마(실측 signal_status·timeline·
        content_type 포함)를 모두 반영했고, 영월군은 실측 신호 상태·타임라인(signal_status·timeline)을 중심으로
        한 메인 사례이며 나머지 항목은 준비 전입니다. 값 옆의 배지로 출처와 목업 여부를 항상 확인하세요.
      </footer>
    </div>
  );
}
