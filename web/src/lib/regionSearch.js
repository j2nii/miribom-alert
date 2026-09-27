// 시군구 검색. 공무원이 실제로 치는 방식을 다 받는다:
//   "강릉" "강릉시"      이름·접미사 없는 이름
//   "강원 고성"          시도 + 이름 (고성군이 강원·경남 두 곳이라 시도로 좁힌다)
//   "경북"               시도만 치면 그 시도 전체
//   "ㄱㄹ" "ㅇㅇㄱ"       초성
//   "영 월"              띄어쓰기가 틀려도 (공백을 빼고 한 번 더 본다)
// 여러 단어는 모두 어딘가에 맞아야 한다(AND). 점수가 높은 순, 같으면 경보 단계가 높은 순.

const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
const HANGUL_START = 0xac00;
const HANGUL_END = 0xd7a3;

export function chosungOf(text) {
  let out = "";
  for (const ch of text) {
    const code = ch.charCodeAt(0);
    out += code >= HANGUL_START && code <= HANGUL_END ? CHO[Math.floor((code - HANGUL_START) / 588)] : ch;
  }
  return out;
}

const isChosungOnly = (token) => /^[ㄱ-ㅎ]+$/.test(token);
const norm = (text) => text.toLowerCase().replace(/\s+/g, "");

// 한 단어가 지역에 얼마나 맞는지. 0이면 안 맞음. matchName은 이름 안에서 강조할 위치
function scoreToken(token, entry) {
  const name = entry.name;
  const short = entry.aliases?.[0] && name.startsWith(entry.aliases[0]) ? entry.aliases[0] : null;

  if (isChosungOnly(token)) {
    const cho = chosungOf(name);
    if (cho === token || (short && chosungOf(short) === token)) return { score: 70, range: [0, token.length] };
    if (cho.startsWith(token)) return { score: 45, range: [0, token.length] };
    const i = cho.indexOf(token);
    if (i >= 0) return { score: 20, range: [i, i + token.length] };
    return null;
  }

  if (name === token) return { score: 100, range: [0, token.length] };
  if (short === token) return { score: 90, range: [0, token.length] };
  if (name.startsWith(token)) return { score: 65, range: [0, token.length] };
  const i = name.indexOf(token);
  if (i >= 0) return { score: 35, range: [i, i + token.length] };

  // 시도: 정식명·약칭·옛 이름("강원도", "전라북도")
  const sidoNames = [entry.sido, entry.sido_short, ...(entry.aliases ?? []).slice(short ? 1 : 0)];
  if (sidoNames.some((s) => s === token)) return { score: 30, sido: true };
  if (sidoNames.some((s) => s.startsWith(token))) return { score: 18, sido: true };
  return null;
}

function scoreEntry(tokens, entry) {
  let total = 0;
  let range = null;
  let onlySido = true;
  for (const token of tokens) {
    const hit = scoreToken(token, entry);
    if (!hit) return null;
    total += hit.score;
    if (hit.range && !range) range = hit.range;
    if (!hit.sido) onlySido = false;
  }
  return { score: total, range, onlySido };
}

const ALERT_RANK = { 심각: 3, 경계: 2, 주의: 1, 관심: 0 };

export function searchRegions(query, regions, limit = 40) {
  const raw = query.trim();
  if (!raw) return [];
  const tokens = raw.toLowerCase().split(/\s+/).filter(Boolean);

  let hits = [];
  for (const entry of regions) {
    const s = scoreEntry(tokens, entry);
    if (s) hits.push({ entry, ...s });
  }
  // "영 월"처럼 띄어쓰기가 틀린 경우: 단어로 못 찾으면 공백을 빼고 한 번 더
  if (hits.length === 0 && tokens.length > 1) {
    const joined = norm(raw);
    for (const entry of regions) {
      const s = scoreEntry([joined], entry);
      if (s) hits.push({ entry, ...s });
    }
  }

  hits.sort(
    (a, b) =>
      b.score - a.score ||
      Number(Boolean(a.entry.disabled)) - Number(Boolean(b.entry.disabled)) ||
      (ALERT_RANK[b.entry.alert] ?? -1) - (ALERT_RANK[a.entry.alert] ?? -1) ||
      a.entry.name.localeCompare(b.entry.name, "ko")
  );
  // 시도만 쳤을 때(예: "경북")는 그 시도 전체를 보여줘야 하므로 한도를 넉넉히
  const allSido = hits.length > 0 && hits.every((h) => h.onlySido);
  return hits.slice(0, allSido ? 60 : limit);
}

// 경보가 높은 지역: 단계 → 초과 신호 수 → 이름
export function topAlertRegions(regions, limit = 8) {
  return regions
    .filter((e) => !e.disabled && (ALERT_RANK[e.alert] ?? 0) >= 1)
    .sort(
      (a, b) =>
        ALERT_RANK[b.alert] - ALERT_RANK[a.alert] ||
        (b.exceeded ?? 0) - (a.exceeded ?? 0) ||
        a.name.localeCompare(b.name, "ko")
    )
    .slice(0, limit);
}

export function alertCounts(regions) {
  const counts = {};
  for (const e of regions) if (!e.disabled && e.alert) counts[e.alert] = (counts[e.alert] ?? 0) + 1;
  return counts;
}
