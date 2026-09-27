import { useEffect, useState } from "react";

// Mirrors the reference demo's header markup/classes exactly (brand /
// brand-tag / app-subtitle). The demo had no area navigation (everything
// was 3 panels on one screen); with 5 areas now spanning a taller page, a
// small anchor row is added below the subtitle, styled like the demo's own
// pill tags rather than as a separate nav bar.
//
// 라벨에 업무 언어를 병기한 이유: "AREA 1"만으로는 처음 온 담당자가 그 화면에서 무엇을
// 하는지 알 수 없다. 번호를 빼지 않은 것은 제출 문서·슬라이드가 AREA 번호로 쓰여 있어서다.
// 이 줄이 화면 전체의 흐름(지금 상황 → 신호 확인 → 원인 → 오늘 할 일 → 성과)을 상시로
// 보여주므로, 투어를 닫은 뒤에도 길잡이가 남는다.
const AREA_ANCHORS = [
  { id: "area0", num: "0", label: "지금 상황" },
  { id: "area1", num: "1", label: "신호 확인" },
  { id: "area2", num: "2", label: "원인 콘텐츠" },
  { id: "area3", num: "3", label: "오늘 할 일" },
  { id: "area4", num: "4", label: "성과 점검" },
];

export default function Header({ onReplayTour, onAsk }) {
  const [activeId, setActiveId] = useState("area0");

  // 지금 보고 있는 구역을 앵커에 표시한다. ChatWidget이 docked/floating 전환에 쓰는 것과
  // 같은 IntersectionObserver 패턴.
  useEffect(() => {
    const sections = AREA_ANCHORS.map((a) => document.getElementById(a.id)).filter(Boolean);
    if (sections.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) setActiveId(visible.target.id);
      },
      // 화면 상단 1/3 지점에 들어온 구역을 "지금 보는 곳"으로 친다
      { rootMargin: "-20% 0px -60% 0px", threshold: [0, 0.2, 0.5] }
    );
    sections.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  // <nav>을 <header> 안에 두면 sticky가 헤더 높이 안에서만 붙어 헤더와 함께 사라진다.
  // 형제로 빼야 페이지 전체를 따라온다.
  return (
    <>
      <header className="app-header">
      <div className="app-header__top">
        <div>
          <div className="brand">
            <span className="brand-name">관광레이더</span>
            <span className="brand-tag">DEMO · 스키마 목업/실데이터 기반</span>
          </div>
          <p className="app-subtitle">
            SNS·검색·방문 신호로 관광객 급증을 미리 잡고, 오늘 할 조치와 보고문까지 받아 가는 화면입니다.
          </p>
        </div>
        <button type="button" className="app-header__help" onClick={onReplayTour}>
          사용법 보기
        </button>
      </div>
      </header>

      <nav className="area-nav">
        <div className="area-nav__inner">
          <div className="area-nav__anchors">
            {AREA_ANCHORS.map((a) => (
              <a
                key={a.id}
                href={`#${a.id}`}
                className={`app-header-anchor${activeId === a.id ? " is-active" : ""}`}
              >
                <span className="app-header-anchor__num">{a.num}</span>
                {a.label}
              </a>
            ))}
          </div>
          {/* 좁은 화면 전용(CSS로 숨김/표시). 모바일에서는 떠다니는 챗봇 아이콘이 본문
              글자를 가려서 아예 없앴고, 그 진입점을 여기로 옮겼다 -- 내비가 화면 상단에
              고정돼 있으므로 어느 위치에서 읽던 중이든 한 번에 닿는다. */}
          <button type="button" className="area-nav__ask" onClick={onAsk}>
            💬 물어보기
          </button>
        </div>
      </nav>
    </>
  );
}
