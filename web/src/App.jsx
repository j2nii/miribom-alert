import { useState } from "react";
import Header from "./components/common/Header.jsx";
import ChatWidget from "./components/common/ChatWidget.jsx";
import { REGIONS } from "./data/manifest.js";
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

  return (
    <div className="app">
      <Header region={region} onRegionChange={setRegion} />
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

        <section id="area1" className="panel panel-scan panel-scroll">
          <Area1SignalScan region={region} />
        </section>

        <section id="area4" className="panel panel-performance">
          <Area4Performance region={region} />
        </section>
      </main>
      <ChatWidget key={region} region={region} regionLabel={REGIONS.find((item) => item.key === region)?.label ?? region} />
      <footer className="app-footer">
        관광레이더 · 실데이터와 목업을 함께 제공하는 데모입니다. 기준일과 출처를 확인하세요.
      </footer>
    </div>
  );
}
