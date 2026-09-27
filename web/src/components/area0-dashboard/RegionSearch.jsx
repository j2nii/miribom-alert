import { useEffect, useId, useMemo, useRef, useState } from "react";
import { keyOf, useRegionIndex } from "../../data/regionIndex.js";
import { alertCounts, searchRegions, topAlertRegions } from "../../lib/regionSearch.js";
import "./regionSearch.css";

// 전국 226개 시군구 검색. 기존 <select>(사례 7곳)를 대신한다.
//
// 편의 장치
//   - 이름·접미사 없는 이름·시도+이름·시도만·초성·띄어쓰기 틀림까지 받는다(lib/regionSearch.js)
//   - 빈 칸일 때: 최근 본 지역 → 심층 사례 지역 → 지금 경보가 높은 지역 → 시도별 둘러보기
//   - 결과마다 경보 단계·심층 사례 여부를 붙여 고르기 전에 상황을 본다
//   - 키보드: / 로 바로 검색, ↑↓ 이동, Enter 선택, Esc 닫기
const RECENT_KEY = "regionSearchRecent";
const RECENT_MAX = 5;
const CASE_ORDER = ["yeongwol", "geoje", "yeosu", "sokcho", "inje", "ulleung"];
const SAMPLE_REGIONS = [{ key: "chungju", label: "충주시", note: "생애주기 참고 사례 · 샘플" }];

function readRecent() {
  try {
    const raw = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function pushRecent(key) {
  try {
    const next = [key, ...readRecent().filter((k) => k !== key)].slice(0, RECENT_MAX);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // 저장이 막힌 환경이면 최근 목록만 빠진다
  }
}

export default function RegionSearch({ region, onRegionChange }) {
  const { status, index } = useRegionIndex();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const wrapRef = useRef(null);
  const listId = useId();

  const current = index?.byKey.get(region);
  const regions = index?.regions ?? [];

  // 목록: 검색어가 있으면 결과, 없으면 추천 묶음
  const sections = useMemo(() => {
    if (!index) return [];
    if (query.trim()) {
      const hits = searchRegions(query, regions);
      return [{ title: hits.length ? `검색 결과 ${hits.length}곳` : null, items: hits.map((h) => ({ entry: h.entry, range: h.range })) }];
    }
    const recent = readRecent()
      .map((k) => index.byKey.get(k))
      .filter((e) => e && keyOf(e) !== region);
    // 주 사례(영월)·대비 사례(거제)를 먼저
    const cases = regions
      .filter((e) => e.case)
      .sort((a, b) => CASE_ORDER.indexOf(a.key) - CASE_ORDER.indexOf(b.key));
    return [
      recent.length && { title: "최근 본 지역", items: recent.map((entry) => ({ entry })) },
      { title: "심층 분석 사례 지역 — 크롤링 자료까지 연결", items: cases.map((entry) => ({ entry })) },
      { title: "지금 경보가 높은 지역", items: topAlertRegions(regions).map((entry) => ({ entry })) },
    ].filter(Boolean);
  }, [index, query, regions, region]);

  const flat = useMemo(() => sections.flatMap((s) => s.items).filter((i) => !i.entry.disabled), [sections]);

  useEffect(() => setActive(0), [query, open]);

  // "/" 로 어디서든 검색창에 바로 들어간다 (입력 중일 때는 제외)
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || document.activeElement?.isContentEditable) return;
      e.preventDefault();
      inputRef.current?.focus();
      setOpen(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // 바깥을 누르면 닫는다
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (!wrapRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // 키보드로 옮긴 항목이 보이게 스크롤
  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const choose = (key) => {
    if (!key) return;
    pushRecent(key);
    onRegionChange(key);
    setQuery("");
    setOpen(false);
    inputRef.current?.blur();
  };

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, flat.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = flat[active];
      if (item) choose(keyOf(item.entry));
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
      inputRef.current?.blur();
    }
  };

  const counts = alertCounts(regions);
  let flatIndex = -1;

  return (
    <div className="region-search" ref={wrapRef}>
      <div className={`region-search__field${open ? " is-open" : ""}`}>
        <span className="region-search__icon" aria-hidden="true">⌕</span>
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && flat[active] ? `${listId}-${active}` : undefined}
          aria-label="시군구 검색"
          value={query}
          placeholder={
            open
              ? "시군구 이름·시도·초성 (예: 강릉, 강원 고성, ㅇㅇ)"
              : current
                ? `${current.sido_short} ${current.name}`
                : "지역을 검색하세요"
          }
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
        />
        {!open && current && <CurrentBadges entry={current} />}
        {query && (
          <button type="button" className="region-search__clear" aria-label="검색어 지우기" onClick={() => { setQuery(""); inputRef.current?.focus(); }}>
            ×
          </button>
        )}
        <kbd className="region-search__kbd" aria-hidden="true">/</kbd>
      </div>

      {open && (
        <div className="region-search__panel">
          {status === "loading" && <p className="region-search__empty">지역 목록을 불러오는 중…</p>}
          {status === "error" && <p className="region-search__empty">지역 목록을 불러오지 못했습니다. 사례 지역만 선택할 수 있습니다.</p>}

          {index && (
            <>
              {!query.trim() && (
                <p className="region-search__summary">
                  전국 <b>{index.count}</b>개 시군구 · 경보{" "}
                  {["경계", "주의", "관심"].filter((l) => counts[l]).map((l) => (
                    <span key={l} className="region-search__count">
                      <i className={`alert-dot alert-dot--${l}`} />
                      {l} {counts[l]}
                    </span>
                  ))}
                  <span className="region-search__asof">· {regions.find((e) => e.alert_as_of)?.alert_as_of} 판정</span>
                </p>
              )}

              <div className="region-search__list" role="listbox" id={listId} ref={listRef}>
                {sections.map((section, si) => (
                  <div key={si} className="region-search__section">
                    {section.title && <p className="region-search__section-title">{section.title}</p>}
                    {section.items.map(({ entry, range }) => {
                      if (entry.disabled) {
                        return (
                          <div key={entry.code} className="region-option is-disabled" aria-disabled="true">
                            <span className="region-option__name">{entry.name}</span>
                            <span className="region-option__note">{entry.note}</span>
                          </div>
                        );
                      }
                      flatIndex += 1;
                      const i = flatIndex;
                      const key = keyOf(entry);
                      return (
                        <div
                          key={`${si}-${key}`}
                          id={`${listId}-${i}`}
                          data-index={i}
                          role="option"
                          aria-selected={i === active}
                          className={`region-option${i === active ? " is-active" : ""}${key === region ? " is-current" : ""}`}
                          onMouseEnter={() => setActive(i)}
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => choose(key)}
                        >
                          <span className="region-option__name">
                            <span>
                              <Highlight text={entry.name} range={range} />
                            </span>
                            <span className="region-option__sido">{entry.sido_short}</span>
                          </span>
                          <span className="region-option__meta">
                            {entry.search_peak && (
                              <span className="region-option__signal" title={`검색 신호 확정 ${entry.search_peak.confirm}`}>
                                검색 {entry.search_peak.peak.toFixed(1)}배
                              </span>
                            )}
                            {entry.case && <span className="region-option__case">심층 사례</span>}
                            {entry.alert && <AlertChip level={entry.alert} />}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ))}

                {query.trim() && flat.length === 0 && (
                  <div className="region-search__empty">
                    <p>‘{query}’와 맞는 시군구가 없습니다.</p>
                    <p className="region-search__tip">시도 이름(예: 경북)이나 초성(예: ㄱㄹ)으로도 찾을 수 있습니다.</p>
                  </div>
                )}

                {!query.trim() && (
                  <div className="region-search__section">
                    <p className="region-search__section-title">시도별로 둘러보기</p>
                    <div className="region-search__sidos">
                      {index.sidos.map((s) => (
                        <button
                          key={s.short}
                          type="button"
                          className="sido-chip"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => {
                            setQuery(`${s.short} `);
                            inputRef.current?.focus();
                          }}
                        >
                          {s.short} <span>{s.count}</span>
                        </button>
                      ))}
                    </div>
                    {SAMPLE_REGIONS.map((s) => (
                      <button key={s.key} type="button" className="region-search__sample" onMouseDown={(e) => e.preventDefault()} onClick={() => choose(s.key)}>
                        {s.label} <span>{s.note}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <p className="region-search__hint">
                <kbd>↑</kbd>
                <kbd>↓</kbd> 이동 · <kbd>Enter</kbd> 선택 · <kbd>Esc</kbd> 닫기 · 어디서든 <kbd>/</kbd> 로 검색
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function CurrentBadges({ entry }) {
  return (
    <span className="region-search__current" aria-hidden="true">
      {entry.case ? <span className="region-option__case">심층 사례</span> : <span className="region-option__basic">데이터랩 기본</span>}
      {entry.alert && <AlertChip level={entry.alert} />}
    </span>
  );
}

function AlertChip({ level }) {
  return (
    <span className={`alert-chip alert-chip--${level}`}>
      <i className={`alert-dot alert-dot--${level}`} />
      {level}
    </span>
  );
}

function Highlight({ text, range }) {
  if (!range) return text;
  const [a, b] = range;
  return (
    <>
      {text.slice(0, a)}
      <mark>{text.slice(a, b)}</mark>
      {text.slice(b)}
    </>
  );
}
