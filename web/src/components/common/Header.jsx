// Mirrors the reference demo's header markup/classes exactly (brand /
// brand-tag / app-subtitle). The demo had no area navigation (everything
// was 3 panels on one screen); with 5 areas now spanning a taller page, a
// small anchor row is added below the subtitle, styled like the demo's own
// pill tags rather than as a separate nav bar.
const AREA_ANCHORS = [
  { href: "#area0", label: "AREA 0" },
  { href: "#trend", label: "신호 추이·예측" },
  { href: "#area1", label: "AREA 1" },
  { href: "#area2", label: "AREA 2" },
  { href: "#area3", label: "AREA 3" },
  { href: "#area4", label: "AREA 4" },
];

export default function Header() {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand-name">관광레이더</span>
        <span className="brand-tag">DEMO · 스키마 목업/실데이터 기반</span>
      </div>
      <p className="app-subtitle">지자체 실무자를 위한 바이럴 조기 감지 &amp; 정책 대응 준비 도구.</p>
      <nav className="app-header-anchors">
        {AREA_ANCHORS.map((a) => (
          <a key={a.href} href={a.href} className="app-header-anchor">
            {a.label}
          </a>
        ))}
      </nav>
    </header>
  );
}
