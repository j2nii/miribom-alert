import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { keyOf, regionLabelOf, useRegionIndex } from "../../data/regionIndex.js";
import { searchRegions, topAlertRegions } from "../../lib/regionSearch.js";

const CASE_ORDER = ["yeongwol", "geoje", "yeosu", "sokcho", "inje", "ulleung"];

export default function RegionSearchPicker({ selected, current, onSelect }) {
  const { status, index } = useRegionIndex();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef(null);
  const input = useRef(null);
  const listId = "region-search-results";

  const results = useMemo(() => {
    if (!index) return [];
    if (query.trim()) return searchRegions(query, index.regions, 12).map((hit) => hit.entry);
    const cases = index.regions.filter((entry) => entry.case)
      .sort((a, b) => CASE_ORDER.indexOf(a.key) - CASE_ORDER.indexOf(b.key));
    const alerts = topAlertRegions(index.regions, 5).filter((entry) => !cases.includes(entry));
    return [...cases, ...alerts];
  }, [index, query]);
  const browsing = !query.trim();
  const caseCount = browsing ? results.filter((entry) => entry.case).length : 0;
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

  function choose(entry) {
    if (entry.disabled) return;
    onSelect(keyOf(entry));
    setQuery("");
    setOpen(false);
    input.current?.blur();
  }

  function onKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((value) => Math.min(value + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((value) => Math.max(value - 1, 0));
    } else if (event.key === "Enter" && open) {
      event.preventDefault();
      if (results[active]) choose(results[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  }

  return <div className="header-region-search" ref={root}>
    <input
      ref={input}
      id="active-region"
      role="combobox"
      aria-label="관심 지역 검색"
      aria-expanded={open}
      aria-controls={listId}
      aria-autocomplete="list"
      aria-activedescendant={open && results[active] ? `${listId}-${active}` : undefined}
      autoComplete="off"
      value={query}
      placeholder={regionLabelOf(selected, index)}
      onFocus={() => setOpen(true)}
      onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
      onKeyDown={onKeyDown}
    />
    {selected !== current && <span className="header-region-pending">선택: {regionLabelOf(selected, index)}</span>}
    {open && <div className="header-region-results" id={listId} role="listbox">
      {status === "loading" && <p>지역 목록을 불러오는 중…</p>}
      {status === "error" && <p>지역 목록을 불러오지 못했습니다.</p>}
      {status === "ok" && <>
        <p className="header-region-results-title">{query.trim() ? `검색 결과 ${results.length}곳` : `전국 ${index.count}개 시군구 · 심층 분석 6곳`}</p>
        {browsing && <p className="header-region-alert-counts">
          {(["경계", "주의", "관심"]).map((level) => <span key={level}>
            <i className="region-alert-dot" data-level={level} aria-hidden="true" />{level} {alertCounts?.[level] ?? 0}
          </span>)}
          <small>· {index.regions.find((entry) => entry.alert_as_of)?.alert_as_of} 판정</small>
        </p>}
        {results.map((entry, i) => <Fragment key={entry.code}>
          {browsing && i === 0 && <p className="header-region-group-title">심층 분석 지역</p>}
          {browsing && i === caseCount && <p className="header-region-group-title">지금 경보가 높은 지역</p>}
          <button
            type="button"
            role="option"
            aria-selected={i === active}
            id={`${listId}-${i}`}
            className={i === active ? "is-active" : ""}
            disabled={entry.disabled}
            onMouseEnter={() => setActive(i)}
            onPointerDown={(event) => { event.preventDefault(); choose(entry); }}
            onClick={() => choose(entry)}
          >
            <span className="region-result-name">{entry.label}<small>{entry.sido_short}</small></span>
            <span className="region-result-badges">
              {entry.case && <span className="region-depth-badge">심층 분석</span>}
              {entry.alert && <span className="region-alert-badge" data-level={entry.alert}><i className="region-alert-dot" data-level={entry.alert} aria-hidden="true" />{entry.alert}</span>}
            </span>
          </button>
        </Fragment>)}
        {results.length === 0 && <p>일치하는 지역이 없습니다. 시도명이나 초성으로도 검색해 보세요.</p>}
      </>}
    </div>}
  </div>;
}
