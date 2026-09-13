// D-04 rule-based briefing generator (docs/설계결정.md).
// Pure function: (already-loaded envelopes) -> { paragraphs, text, charCount }.
// No network call, no invented numbers -- every figure and manual page
// citation traces back to a field on the input objects. Replaces the old
// demo's live, unauthenticated fetch("https://api.anthropic.com/...").
//
// Contract (see plan's "충주/데이터 매핑" section for the rationale):
// - exactly 3 paragraphs: 상황 / 전개 / 조치
// - action list capped at 3 items, each ending in "(매뉴얼 p.N)"
// - every predicted number is paired with its lower/upper band
// - never writes "AI가 분석한" or similar self-reference
// - if checklist has no items, falls back to a fixed sentence instead of
//   fabricating an action
export function generateBriefing({ signalStatus, forecast, checklist, region }) {
  const s = signalStatus.data;
  const f = forecast?.data;
  const c = checklist?.data;

  const p1 = buildSituationParagraph(s, region);
  const p2 = buildOutlookParagraph(f);
  const p3 = buildActionParagraph(c);

  const paragraphs = [p1, p2, p3];
  const text = paragraphs.join("\n\n");

  return { paragraphs, text, charCount: text.length };
}

function buildSituationParagraph(s, regionLabel) {
  const { exceeded_count, total } = s.agreement;
  const transition =
    s.previous_alert_level && s.previous_alert_level !== s.alert_level
      ? `${s.previous_alert_level}에서 ${s.alert_level}로 상향되었다`
      : `${s.alert_level} 단계를 유지하고 있다`;

  return (
    `${regionLabel}의 관광지 혼잡 경보는 독립 신호 ${total}개 중 ${exceeded_count}개가 임계치를 초과해 ` +
    `${transition}. ${s.basis}`
  );
}

function buildOutlookParagraph(f) {
  if (!f) {
    return "예측 데이터가 없어 향후 전개는 현재 판단하지 않는다.";
  }
  const peak = f.peak_days?.[0];
  if (!peak) {
    return "당분간 뚜렷한 피크 없이 현재 수준이 유지될 것으로 예측된다.";
  }
  const daily = f.daily?.find((d) => d.date === peak.date);
  const band = daily ? `(${daily.lower.toLocaleString()}~${daily.upper.toLocaleString()}명 구간)` : "";

  return (
    `예측 모델(${f.model.name}, 검증 ${f.model.metric.name} ${f.model.metric.value})에 따르면 ` +
    `${peak.date}에 방문객이 ${peak.predicted.toLocaleString()}명 ${band}까지 늘어 ` +
    `예상 경보 ${peak.expected_alert_level} 단계에 이를 것으로 전망된다. ${peak.reason}.`
  );
}

function buildActionParagraph(c) {
  const items = (c?.items ?? []).slice().sort((a, b) => a.rank - b.rank).slice(0, 3);
  if (items.length === 0) {
    return "해당 조건에 매칭된 조치가 없어 별도 대응 항목을 제시하지 않는다.";
  }

  const lines = items.map(
    (item, i) =>
      `${i + 1}) ${item.action}(담당: ${item.owner}, 매뉴얼 p.${item.manual_ref.page})`
  );

  return `우선 대응 조치는 다음과 같다. ${lines.join(" ")}`;
}
