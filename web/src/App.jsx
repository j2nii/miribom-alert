import { useState } from "react";
import Header from "./components/common/Header.jsx";
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
  const [region, setRegion] = useState("geoje");

  return (
    <div className="app">
      <Header />
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
        이 화면은 목업/실데이터가 혼재된 데모입니다. 거제시는 9종 데이터 스키마(실측 content_type 포함)를,
        나머지 지역은 예시 데이터를 반영했습니다. 값 옆의 배지로 출처와 목업 여부를 항상 확인하세요.
      </footer>
    </div>
  );
}
