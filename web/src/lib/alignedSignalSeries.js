// Compare search and visitors on the latest date both sources cover.
// Each region export supplies its own search and visitor coverage dates.
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
