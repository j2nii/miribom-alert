// Compare search and visitors on the latest date both sources cover.
// This is 2026-08-14 in the current web export and will move forward when
// both source dates are refreshed together.
export function alignedSignalSeries(data) {
  const searchEnd = data?.as_of?.search;
  const visitorEnd = data?.as_of?.visitors;
  const commonEnd = searchEnd && visitorEnd
    ? (searchEnd < visitorEnd ? searchEnd : visitorEnd)
    : null;
  const daily = data?.daily ?? [];
  return {
    commonEnd,
    daily: commonEnd ? daily.filter((row) => row.date <= commonEnd) : daily,
  };
}
