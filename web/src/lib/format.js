export function timestampForFilename(date = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_` +
    `${pad(date.getHours())}${pad(date.getMinutes())}`
  );
}

export function downloadTextFile(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const WEEKDAY_KR = ["일", "월", "화", "수", "목", "금", "토"];

// "2026-09-19" -> "토". 날짜 문자열을 그대로 Date에 넣으면 UTC로 해석돼 KST에서 하루
// 밀리므로 T00:00:00을 붙여 로컬 자정으로 고정한다.
export function weekdayOf(isoDate) {
  if (typeof isoDate !== "string") return null;
  const d = new Date(`${isoDate.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : WEEKDAY_KR[d.getDay()];
}

export function isWeekend(isoDate) {
  const w = weekdayOf(isoDate);
  return w === "토" || w === "일";
}

// 피크 예상일처럼 "주말인지"가 바로 판단에 쓰이는 날짜에 요일을 붙인다.
export function formatDateWithWeekday(isoDate) {
  const w = weekdayOf(isoDate);
  return w ? `${isoDate} (${w})` : isoDate;
}
