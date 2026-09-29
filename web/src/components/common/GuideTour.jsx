import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useMediaQuery, NARROW_QUERY } from "../../hooks/useMediaQuery.js";

// 처음 들어온 담당자에게 화면 사용 순서를 한 바퀴 보여주는 스포트라이트 투어.
//
// 구멍을 뚫는 방식: 대상 요소의 사각형에 맞춘 빈 div에 `box-shadow: 0 0 0 9999px <어두운색>`을
// 준다. 그림자가 화면 전체를 덮고 사각형 안쪽만 그대로 남아서, 별도의 SVG 마스크나 라이브러리
// 없이 "대상만 선명하고 나머지는 반투명"이 된다.
//
// 대상은 선택자로 찾는다 -- 단계가 AREA0~4에 흩어져 있어 ref를 끌어올리면 App 전체에 배선이
// 생긴다. ChatWidget이 `.app-grid`를 직접 조회하는 기존 선례와 같은 방식이고, 선택자가 없는
// 지역(영월은 브리핑 없음 등)에서는 해당 단계를 조용히 건너뛴다.
const STORAGE_KEY = "guideTourSeen";
const VERSION = "v1";
const PADDING = 8; // 구멍을 대상보다 조금 넉넉하게
const CARD_WIDTH = 320;
const CARD_GAP = 14;

const STEPS = [
  {
    // selector가 없는 단계 = 스포트라이트 없이 화면 가운데에 띄우는 소개. 무엇을 가리킬지
    // 정하기 전에 "이 화면이 무엇을 위한 것인지"부터 알려야, 뒤따르는 단계들이 각각
    // 어디에 쓰이는 조각인지 이해된다.
    intro: true,
    title: "관광레이더는 이런 서비스입니다",
    body: "SNS·검색·이동통신 데이터에서 관광객이 몰릴 신호를 미리 잡아내고, 그 상황에 맞는 대응 조치를 매뉴얼 근거와 함께 전달합니다. 혼잡이 벌어진 뒤 수습하는 게 아니라, 벌어지기 전에 준비할 시간을 만드는 것이 목표입니다.",
    points: [
      "지금 우리 지역이 어느 경보 단계인지",
      "왜 그렇게 판단했는지 — 출처가 다른 신호 3개",
      "오늘 무엇을 해야 하는지 — 매뉴얼 쪽수까지",
      "그 대응이 실제로 효과가 있었는지",
    ],
    note: "화면의 모든 수치에는 출처와 실측·샘플 표시가 붙습니다. 조치 문구는 매뉴얼 원문을 그대로 인용하며, 없는 내용을 지어내지 않습니다.",
  },
  {
    selector: ".region-search, .scan-input-wrap",
    title: "담당 지역을 찾습니다",
    body: "전국 226개 시군구를 이름·시도·초성(예: 강릉, 강원 고성, ㄱㄹ)으로 찾을 수 있고, 목록에서 지금 경보 단계도 함께 보입니다. 어디서든 / 키로 바로 검색합니다. 지역을 바꾸면 아래 모든 화면과 대화창이 함께 바뀌고, 대화 기록도 새로 시작됩니다.",
  },
  {
    // 게이지·배지·기준일·단계 설명을 묶은 영역(SignalStatusPanel/LifecyclePanel의
    // .alert-summary). 설명 문구가 바늘을 언급하므로 바늘이 스포트라이트 밖에 있으면 안 된다.
    selector: ".alert-summary, .area0-layout__main",
    title: "지금 어떤 상태인지 봅니다",
    body: "게이지 바늘이 가리키는 곳이 오늘의 경보 단계이고, 바로 아래 한 줄이 그 단계에서 무엇을 해야 하는지입니다. 옆의 기준일은 이 판정이 언제 것인지를 뜻합니다.",
  },
  {
    selector: ".today-action",
    title: "오늘 할 일을 여기서 받습니다",
    body: "상황 유형과 오늘 처리할 조치 건수, 그중 먼저 할 3건이 정리돼 있습니다. 버튼을 누르면 전체 목록으로 이동하고, 요약은 바로 복사할 수 있습니다.",
  },
  {
    // 화면 상태에 따라 대화창이 어떤 모습으로 있든 하나는 잡히게 한다: 펼쳐진 패널 →
    // 모바일 상단 내비의 "물어보기" 버튼 → 데스크톱 플로팅 아이콘.
    selector: ".chat-widget, .area-nav__ask, .chat-widget__toggle",
    title: "모르면 물어보세요",
    body: "용어나 수치가 낯설면 평소 말로 물어보면 됩니다. 답변 아래에는 어떤 데이터를 근거로 했는지, 실측인지 샘플인지가 항상 붙습니다. 화면을 내린 뒤에는 위쪽 '물어보기' 버튼으로 다시 열 수 있습니다.",
  },
  {
    // 신호 추이·예측 패널(AREA 0 바로 아래). 패널 전체는 화면보다 커서 첫 차트만 비춘다
    selector: "#trend .trend-chart, #trend",
    title: "신호가 실제로 어떻게 움직였는지 봅니다",
    body: "위 칸은 검색 관심(전년 대비 배율)과 기준선, 아래 칸은 실제 외지인 방문자입니다. 번호 핀은 콘텐츠 확산·혼잡·조치 같은 사건입니다. 이어서 관광지점과 시군구 전체를 비교한 그래프, 7일 방문객 예측이 나옵니다.",
  },
  {
    // 패널 전체(#area1)가 아니라 첫 섹션(3중 교차검증 신호등)을 비춘다 -- 패널은 화면보다
    // 커서 통째로 비추면 스포트라이트가 아무것도 좁혀 주지 못한다.
    selector: "#area1 .section-block, #area1",
    title: "왜 그렇게 판단했는지 확인합니다",
    body: "서로 다른 출처의 신호 3개(관심·의도·실현) 중 몇 개가 기준선을 넘었는지로 단계가 정해집니다. 보고할 때 근거로 쓰는 화면입니다.",
  },
  {
    selector: ".checklist-progress, #area3",
    title: "체크하며 처리하고 보고문을 가져갑니다",
    body: "조치마다 매뉴얼 근거가 붙어 있습니다. 처리한 항목을 체크하면 진행률이 위 '오늘의 결론' 카드에도 반영됩니다. 아래 정책 브리핑은 그대로 복사해 보고서에 붙일 수 있습니다.",
  },
];

export function hasSeenTour() {
  try {
    return localStorage.getItem(STORAGE_KEY) === VERSION;
  } catch {
    return false;
  }
}

function markSeen() {
  try {
    localStorage.setItem(STORAGE_KEY, VERSION);
  } catch {
    // 저장이 막힌 환경이면 매번 뜨는 편이 안 뜨는 것보다 낫다
  }
}

// 쉼표로 여러 선택자를 줄 수 있다 -- 앞쪽이 우선이고, 없으면 다음 것으로 넘어간다.
function findTarget(selector) {
  for (const part of selector.split(",")) {
    const el = document.querySelector(part.trim());
    if (el) return el;
  }
  return null;
}

export default function GuideTour({ open, onClose }) {
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState(null);
  // 열릴 때 한 번만 추려서 고정한다. 매 렌더마다 다시 필터링하면 데이터가 늦게 도착해
  // 단계가 생기거나 사라질 때 진행 중인 인덱스가 다른 단계를 가리키게 된다.
  const [steps, setSteps] = useState([]);
  const [sheetHeight, setSheetHeight] = useState(0);
  const cardRef = useRef(null);
  const isNarrow = useMediaQuery(NARROW_QUERY);

  const step = steps[index];

  const measure = useCallback(() => {
    if (!step) return;
    // 소개 단계는 비출 대상이 없다 -- 구멍 없이 전체를 어둡게 두고 카드만 가운데 띄운다.
    if (!step.selector) {
      setRect(null);
      return;
    }
    const el = findTarget(step.selector);
    if (!el) return;
    const r = el.getBoundingClientRect();
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    // 좁은 화면에서 설명 카드는 하단 시트다. 그 높이를 알아야 구멍을 시트 위로 잘라
    // 하이라이트가 카드에 가리지 않게 할 수 있다.
    if (cardRef.current) setSheetHeight(cardRef.current.offsetHeight);
  }, [step]);

  useEffect(() => {
    if (!open) {
      setSteps([]);
      return;
    }
    // 안내는 맨 위에서 시작한다. 스크롤된 채로 열면 첫 단계가 화면 밖에 있고,
    // 챗봇이 접혀 있는 등 화면 상태가 들쭉날쭉해진다.
    window.scrollTo({ top: 0, behavior: "auto" });
    // 맨 위로 올린 *다음* 단계를 확정한다. 브라우저가 새로고침 때 이전 스크롤 위치를
    // 복원하면 AREA0가 화면 밖이고, 그 상태에서는 모바일 대화창이 렌더되지 않아
    // 해당 단계가 통째로 빠진다. IntersectionObserver 재평가까지 한 박자 기다린다.
    const timer = setTimeout(() => {
      // 지금 화면에 실제로 존재하는 단계만 남긴다 -- 지역마다 없는 패널이 있다
      // (영월은 브리핑이 없고, 충주는 생애주기 스키마라 구성이 다르다).
      // selector가 없는 소개 단계는 조건 없이 남긴다.
      setSteps(STEPS.filter((s) => !s.selector || findTarget(s.selector)));
      setIndex(0);
    }, 150);
    return () => clearTimeout(timer);
  }, [open]);

  // 대상을 화면 가운데로 끌어온 뒤 위치를 잰다. 스크롤이 끝나기 전에 재면 엉뚱한 곳에
  // 구멍이 뚫리므로 스크롤 이벤트가 잦아들 때까지 몇 프레임 더 따라간다.
  useLayoutEffect(() => {
    if (!open || !step) return;
    // 소개 단계는 비출 대상이 없으므로 스크롤도 측정도 하지 않는다.
    if (!step.selector) {
      setRect(null);
      return;
    }
    const el = findTarget(step.selector);
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    measure();
    let frames = 0;
    let raf = requestAnimationFrame(function tick() {
      measure();
      frames += 1;
      if (frames < 40) raf = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(raf);
  }, [open, step, measure]);

  useEffect(() => {
    if (!open) return;
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [open, measure]);

  const finish = useCallback(() => {
    markSeen();
    onClose();
  }, [onClose]);

  const next = useCallback(() => {
    setIndex((i) => (i + 1 < steps.length ? i + 1 : i));
    if (index + 1 >= steps.length) finish();
  }, [index, steps.length, finish]);

  const prev = useCallback(() => setIndex((i) => Math.max(0, i - 1)), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") finish();
      else if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // 본문 스크롤은 일부러 잠그지 않는다 -- 잠그면 각 단계의 scrollIntoView가 먹지 않는다.
    // 대신 위의 scroll 리스너가 구멍을 대상에 계속 붙여 둔다.
  }, [open, finish, next, prev]);

  if (!open || !step) return null;

  // 구멍을 화면 안으로 자른다. 대상이 뷰포트보다 큰 패널이면(AREA3는 3000px가 넘는다)
  // 자르지 않을 경우 구멍이 화면 밖까지 뻗어 어두워지는 곳이 없어지고, 스포트라이트가
  // 아무것도 가리키지 못한다.
  const hole = rect
    ? (() => {
        // 좁은 화면에서는 하단 시트가 차지하는 높이를 빼고 그 위에서만 구멍을 낸다.
        const safeBottom =
          window.innerHeight - 8 - (isNarrow && sheetHeight ? sheetHeight + 24 : 0);
        const top = Math.max(8, rect.top - PADDING);
        const left = Math.max(8, rect.left - PADDING);
        const bottom = Math.min(safeBottom, rect.top + rect.height + PADDING);
        const right = Math.min(window.innerWidth - 8, rect.left + rect.width + PADDING);
        return {
          top,
          left,
          width: Math.max(0, right - left),
          height: Math.max(0, bottom - top),
        };
      })()
    : null;

  // 설명 카드 위치: 넓은 화면에서는 구멍의 오른쪽(자리가 없으면 왼쪽), 좁은 화면에서는
  // 아래쪽 고정 시트.
  // 설명 카드는 구멍을 가리면 안 된다. 오른쪽 → 아래 → 위 → 왼쪽 순으로 자리를 찾는다.
  // (전에는 무조건 좌우만 봐서, 화면 폭을 꽉 채우는 대상에서는 카드가 하이라이트 위에 얹혔다.)
  const CARD_MIN_HEIGHT = 230;
  let cardStyle = { position: "fixed", bottom: 16, left: 16, right: 16 };
  if (!isNarrow && hole) {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const clampLeft = (x) => Math.min(Math.max(CARD_GAP, x), vw - CARD_WIDTH - CARD_GAP);
    const clampTop = (y) => Math.min(Math.max(CARD_GAP, y), vh - CARD_MIN_HEIGHT - CARD_GAP);

    if (vw - (hole.left + hole.width) > CARD_WIDTH + CARD_GAP * 2) {
      cardStyle = { top: clampTop(hole.top), left: hole.left + hole.width + CARD_GAP };
    } else if (vh - (hole.top + hole.height) > CARD_MIN_HEIGHT + CARD_GAP) {
      cardStyle = { top: hole.top + hole.height + CARD_GAP, left: clampLeft(hole.left) };
    } else if (hole.top > CARD_MIN_HEIGHT + CARD_GAP) {
      cardStyle = { bottom: vh - hole.top + CARD_GAP, left: clampLeft(hole.left) };
    } else {
      cardStyle = { top: clampTop(hole.top), left: clampLeft(hole.left - CARD_WIDTH - CARD_GAP) };
    }
    cardStyle = { position: "fixed", width: CARD_WIDTH, ...cardStyle };
  }

  return (
    <div className="tour" role="dialog" aria-modal="true" aria-label="사용법 안내">
      {hole && hole.height > 0 && <div className="tour__hole" style={hole} />}
      {/* 구멍이 아직 측정 전이면 전체를 덮어 화면이 번쩍이지 않게 한다 */}
      {(!hole || hole.height <= 0) && <div className="tour__backdrop" />}

      <div
        className={`tour__card${step.intro ? " tour__card--intro" : ""}`}
        style={step.intro ? undefined : cardStyle}
        ref={cardRef}
      >
        <p className="tour__progress">
          {index + 1} / {steps.length}
        </p>
        <p className="tour__title">{step.title}</p>
        <p className="tour__body">{step.body}</p>
        {step.points && (
          <ul className="tour__points">
            {step.points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
        {step.note && <p className="tour__note">{step.note}</p>}
        <div className="tour__buttons">
          <button type="button" className="tour__skip" onClick={finish}>
            건너뛰기
          </button>
          <div className="tour__nav">
            {index > 0 && (
              <button type="button" className="btn-ghost" onClick={prev}>
                이전
              </button>
            )}
            <button type="button" className="btn-primary" onClick={next}>
              {index + 1 === steps.length ? "시작하기" : step.intro ? "둘러보기" : "다음"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
