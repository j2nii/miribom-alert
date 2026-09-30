import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { keyOf, regionLabelOf, useRegionIndex } from "../../data/regionIndex.js";
import { searchRegions, topAlertRegions } from "../../lib/regionSearch.js";

const CASE_ORDER = ["yeongwol", "geoje", "yeosu", "sokcho", "inje", "ulleung"];
const RECENT_KEY = "regionSearchRecent";
const RECENT_MAX = 5;

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
    localStorage.setItem(RECENT_KEY, JSON.stringify([key, ...readRecent().filter((k) => k !== key)].slice(0, RECENT_MAX)));
  } catch {
    // 사생활 보호 모드 등 저장이 막힌 환경이면 최근 목록만 빠진다
  }
}

export default function RegionSearchPicker({ selected, current, onSelect }) {
  const { status, index } = useRegionIndex();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [recent, setRecent] = useState(readRecent);
  const root = useRef(null);
  const input = useRef(null);
  const list = useRef(null);
  const listId = "region-search-results";
  const browsing = !query.trim();

  // 검색어가 없을 때는 최근 본 지역 → 심층 사례 → 경보 높은 지역 순으로 묶어 보여준다.
  // 검색어가 있으면 한 묶음으로 내려간다.
  const sections = useMemo(() => {
    if (!index) return [];
    if (!browsing) return [{ title: null, items: searchRegions(query, index.regions).map((hit) => hit.entry) }];
    const seen = new Set([current]);
    const recentEntries = recent
      .map((key) => index.byKey.get(key))
      // 같은 지역을 코드와 이름 두 가지로 저장했을 수 있다(51750 / yeongwol) -- 한 번만 싣는다
      .filter((entry) => entry && !seen.has(keyOf(entry)) && seen.add(keyOf(entry)));
    const cases = index.regions
      .filter((entry) => entry.case)
      .sort((a, b) => CASE_ORDER.indexOf(a.key) - CASE_ORDER.indexOf(b.key));
    const alerts = topAlertRegions(index.regions, 5).filter((entry) => !entry.case);
    return [
      recentEntries.length ? { title: "최근 본 지역", items: recentEntries } : null,
      { title: "심층 분석 지역", items: cases },
      { title: "지금 경보가 높은 지역", items: alerts },
    ].filter(Boolean);
  }, [index, query, browsing, current, recent]);

  // 키보드 이동은 묶음을 가로질러 하나의 목록처럼 움직인다.
  const flat = useMemo(() => sections.flatMap((section) => section.items).filter((entry) => !entry.disabled), [sections]);
  const alertCounts = index?.regions.reduce((counts, entry) => {
    if (entry.alert) counts[entry.alert] = (counts[entry.alert] ?? 0) + 1;
    return counts;
  }, {});

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => { if (!root.current?.contains(event.target)) setOpen(false); };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);
  // 묶음이 늘어 목록이 길어졌다 -- 키보드로 옮긴 항목이 보이는 범위를 벗어나지 않게 따라간다.
  useEffect(() => {
    list.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function choose(entry) {
    if (entry.disabled) return;
    const key = keyOf(entry);
    pushRecent(key);
    setRecent(readRecent());
    onSelect(key);
    setQuery("");
    setOpen(false);
    input.current?.blur();
  }

  // 시도 칩은 그 시도 이름을 검색어로 넣는다. searchRegions가 시도만 친 질의를
  // 알아보고 그 시도 전체를 돌려준다(한도도 60으로 넓힌다).
  function browseSido(sido) {
    setQuery(`${sido.short} `);
    setOpen(true);
    input.current?.focus();
  }

  function onKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((value) => Math.min(value + 1, flat.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((value) => Math.max(value - 1, 0));
    } else if (event.key === "Enter" && open) {
      event.preventDefault();
      if (flat[active]) choose(flat[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  }

  let cursor = -1; // flat 인덱스. 묶음을 가로질러 이어서 센다.

  return <div className="header-region-search" ref={root}>
    <input
      ref={input}
      id="active-region"
      role="combobox"
      aria-label="관심 지역 검색"
      aria-expanded={open}
      aria-controls={listId}
      aria-autocomplete="list"
      aria-activedescendant={open && flat[active] ? `${listId}-${active}` : undefined}
      autoComplete="off"
      value={query}
      placeholder={regionLabelOf(selected, index)}
      onFocus={() => setOpen(true)}
      onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
      onKeyDown={onKeyDown}
    />
    {selected !== current && <span className="header-region-pending">선택: {regionLabelOf(selected, index)}</span>}
    {open && <div className="header-region-results" id={listId} role="listbox" ref={list}>
      {status === "loading" && <p>지역 목록을 불러오는 중…</p>}
      {status === "error" && <p>지역 목록을 불러오지 못했습니다.</p>}
      {status === "ok" && <>
        <p className="header-region-results-title">{browsing ? `전국 ${index.count}개 시군구 · 심층 분석 6곳` : `검색 결과 ${flat.length}곳`}</p>
        {browsing && <p className="header-region-alert-counts">
          {(["경계", "주의", "관심"]).map((level) => <span key={level}>
            <i className="region-alert-dot" data-level={level} aria-hidden="true" />{level} {alertCounts?.[level] ?? 0}
          </span>)}
          <small>· {index.regions.find((entry) => entry.alert_as_of)?.alert_as_of} 판정</small>
        </p>}

        {sections.map((section) => <Fragment key={section.title ?? "results"}>
          {section.title && <p className="header-region-group-title">{section.title}</p>}
          {section.items.map((entry) => {
            if (entry.disabled) return null;
            cursor += 1;
            const i = cursor;
            return <button
              key={entry.code}
              type="button"
              role="option"
              aria-selected={i === active}
              id={`${listId}-${i}`}
              data-index={i}
              className={i === active ? "is-active" : ""}
              onMouseEnter={() => setActive(i)}
              onPointerDown={(event) => { event.preventDefault(); choose(entry); }}
              onClick={() => choose(entry)}
            >
              <span className="region-result-name">{entry.name}<small>{entry.sido_short}</small></span>
              <span className="region-result-badges">
                {entry.case && <span className="region-depth-badge">심층 분석</span>}
                {entry.alert && <span className="region-alert-badge" data-level={entry.alert}><i className="region-alert-dot" data-level={entry.alert} aria-hidden="true" />{entry.alert}</span>}
              </span>
            </button>;
          })}
        </Fragment>)}

        {/* 타이핑 없이도 전국을 훑을 수 있는 입구. 시도를 고르면 그 안에서 다시 고른다. */}
        {browsing && index.sidos?.length > 0 && <>
          <p className="header-region-group-title">시도별로 둘러보기</p>
          <div className="header-region-sidos">
            {index.sidos.map((sido) => <button
              key={sido.short}
              type="button"
              onPointerDown={(event) => event.preventDefault()}
              onClick={() => browseSido(sido)}
            >
              {sido.short} <span>{sido.count}</span>
            </button>)}
          </div>
        </>}

        {flat.length === 0 && <p>일치하는 지역이 없습니다. 시도명이나 초성으로도 검색해 보세요.</p>}
      </>}
    </div>}
  </div>;
}
