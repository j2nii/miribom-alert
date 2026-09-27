// 챗봇 답변에서 **강조**가 별표째로 노출되던 문제를 고치는 전처리.
//
// 간헐적 버그가 아니라 CommonMark의 delimiter flanking 규칙이 한국어 본문과 부딪히는
// 결정론적 케이스다. 닫는 `**`는 "바로 앞이 공백이 아니고, (바로 앞이 구두점이 아니거나
// 바로 뒤가 공백/구두점)"일 때만 닫힘으로 인정된다.
//   **'주의'**이며   -> 닫는 `**` 앞이 `'`(구두점), 뒤가 `이`(문자) => 닫힘 불인정
//   **+24.5%**로     -> 닫는 `**` 앞이 `%`(구두점), 뒤가 `로`(문자) => 닫힘 불인정
// 영어에서는 닫는 별표 뒤가 보통 공백이라 잘 드러나지 않지만, 한국어는 조사가 바로
// 붙기 때문에 수치·인용을 강조할 때마다 터진다. 여는 `**` 쪽도 좌우가 뒤집힌 같은 규칙.
//
// 해결: 규칙을 깨는 쪽의 구두점만 마커 *바깥*으로 밀어낸다. 강조되는 알맹이는 유지되고
// 파싱은 성공한다(`**'주의'**이며` -> `'**주의**'이며`). 이미 정상 파싱되는 문자열은
// 한 글자도 건드리지 않는다 -- 멀쩡한 강조 범위를 옮겨 놓지 않기 위한 조건이다.

const EMPHASIS = /\*\*([^*]+)\*\*/g;

// CommonMark가 말하는 "구두점": ASCII 구두점 전체 + 유니코드 구두점 카테고리(\p{P}).
// \p{P}가 중요한 이유는 한국어 답변에 「」·『』·… 같은 CJK 문장부호가 자주 섞이기 때문이다.
// ASCII와 둥근 따옴표만 보던 이전 버전은 **「주의」**를 처럼 CJK 괄호가 마커에 붙은 경우를
// 놓쳐서 별표가 그대로 노출됐다. (\p{S}는 넣지 않는다 -- CommonMark 0.30의 정의에 없고,
// 이미 정상 파싱되는 문자열을 괜히 건드리게 된다.)
const ASCII_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
const UNICODE_PUNCT = /\p{P}/u;
const SPACE = /\s/;

// 닫는 기호 -> 여는 기호. 아래 fixOne에서 짝을 함께 밖으로 밀어낼 때 쓴다.
const PAIR_OPENER = {
  "'": "'",
  '"': '"',
  ")": "(",
  "]": "[",
  "}": "{",
  "’": "‘", // ’ ‘
  "”": "“", // ” “
  "」": "「", // 」 「
  "』": "『", // 』 『
  "〉": "〈", // 〉 〈
  "》": "《", // 》 《
  "】": "【", // 】 【
  "〕": "〔", // 〕 〔
  "）": "（", // ） （
};

function isPunct(ch) {
  return !!ch && (ASCII_PUNCT.includes(ch) || UNICODE_PUNCT.test(ch));
}
function isSpace(ch) {
  return !!ch && SPACE.test(ch);
}

function fixOne(inner, prev, next) {
  let lead = "";
  let trail = "";
  let core = inner;

  // 마커 안쪽이 공백으로 시작/끝나면 어떤 경우에도 강조로 파싱되지 않는다.
  while (core && isSpace(core[0])) {
    lead += core[0];
    core = core.slice(1);
  }
  while (core && isSpace(core[core.length - 1])) {
    trail = core[core.length - 1] + trail;
    core = core.slice(0, -1);
  }

  // 여는 `**`가 left-flanking이 되지 못하는 조건: 안쪽 첫 글자가 구두점이고, 마커 앞이
  // 공백도 구두점도 아닌 실제 문자일 때.
  while (core && isPunct(core[0]) && prev && !isSpace(prev) && !isPunct(prev)) {
    lead += core[0];
    core = core.slice(1);
  }
  // 닫는 `**`가 right-flanking이 되지 못하는 조건: 안쪽 끝 글자가 구두점이고, 마커 뒤가
  // 공백도 구두점도 아닌 실제 문자일 때(한국어 조사가 붙는 바로 그 경우).
  while (core && isPunct(core[core.length - 1]) && next && !isSpace(next) && !isPunct(next)) {
    trail = core[core.length - 1] + trail;
    core = core.slice(0, -1);
  }

  // 따옴표·괄호처럼 짝이 있는 기호는 한쪽만 밖으로 나가면 `**'주의**'이며`처럼 강조가
  // 비뚤어져 보인다. 닫는 쪽이 밀려났고 여는 쪽이 그 짝이면 같이 밖으로 내보낸다.
  if (core && trail && PAIR_OPENER[trail[0]] === core[0]) {
    lead += core[0];
    core = core.slice(1);
  }

  // 알맹이가 없으면(구두점/공백만 감싼 경우) 마커만 버리고 내용은 살린다.
  if (!core) return lead + trail;
  return `${lead}**${core}**${trail}`;
}

export function normalizeMarkdown(text) {
  if (!text) return "";
  let out = text.replace(EMPHASIS, (match, inner, offset, whole) =>
    fixOne(inner, whole[offset - 1], whole[offset + match.length])
  );

  // 모델이 문단 경계에 `|`를 하나 흘리는 경우가 있다(실제 답변에서 관측:
  // "...로 둔다(에이전트③ 기준).|"). 표 문법이 아니라 단독 문자라 마크다운은 그대로
  // 글자로 찍고, 화면에는 정체불명의 막대기가 남는다. 한 줄에 `|`가 하나뿐이고 줄 끝이나
  // 줄 머리에 있을 때만 지운다 -- 진짜 표라면 한 줄에 여러 개가 있으므로 건드리지 않는다.
  out = out
    .split("\n")
    .map((line) => ((line.match(/\|/g) ?? []).length === 1 ? line.replace(/^\s*\||\|\s*$/, "") : line))
    .join("\n");

  // 스트리밍 중에는 여는 `**`만 도착한 순간이 있다 -- 짝이 없는 마지막 마커는 렌더 전에
  // 지워서 타이핑 도중 별표가 번쩍이지 않게 한다.
  const markerCount = out.split("**").length - 1;
  if (markerCount % 2 === 1) {
    const last = out.lastIndexOf("**");
    out = out.slice(0, last) + out.slice(last + 2);
  }
  return out;
}
