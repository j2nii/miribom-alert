// Shared loading/error/unsupported rendering for a useRegionData() result.
// Pass a render function that receives { envelope, kind } once status "ok".
export default function DataState({ result, render }) {
  if (result.status === "loading") {
    return <div className="loading-state">불러오는 중…</div>;
  }
  if (result.status === "unsupported") {
    return <div className="unsupported-state">이 지역은 {result.dataType} 데이터가 준비되지 않았습니다.</div>;
  }
  if (result.status === "error") {
    return <div className="error-state">데이터를 불러오지 못했습니다 ({result.error}).</div>;
  }
  return render(result);
}
