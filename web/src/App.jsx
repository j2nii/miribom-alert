import { useEffect, useState } from "react";
import Header from "./components/common/Header.jsx";
import GuideTour, { hasSeenTour } from "./components/common/GuideTour.jsx";
import Area0Dashboard from "./pages/Area0Dashboard.jsx";
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
  const [region, setRegion] = useState("yeongwol");
  const [tourOpen, setTourOpen] = useState(false);

  // 첫 방문이면 사용법 투어를 자동으로 연다. 바로 열지 않고 한 박자 기다리는 이유:
  // 투어 단계가 화면에 실제로 있는 요소만 골라 잡는데, 정적 JSON이 도착하기 전에는
  // "오늘의 결론" 카드 같은 단계가 아직 렌더되지 않아 통째로 빠진다.
  useEffect(() => {
    if (hasSeenTour()) return;
    const timer = setTimeout(() => setTourOpen(true), 900);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="app">
      <Header onReplayTour={() => setTourOpen(true)} />
      <div className="app-grid">
        <section id="area0" className="panel panel-dashboard">
          <Area0Dashboard region={region} onRegionChange={setRegion} />
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

      <GuideTour open={tourOpen} onClose={() => setTourOpen(false)} />
    </div>
  );
}
