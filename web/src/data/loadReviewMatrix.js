const REVIEW_MATRIX_URL = "/prod/review_matrix_latest.json";

export async function loadReviewMatrix() {
  const response = await fetch(REVIEW_MATRIX_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`2x2 상태 파일을 불러오지 못했습니다 (${response.status})`);
  }
  const payload = await response.json();
  if (!Array.isArray(payload?.data?.regions) || !payload.data.summary ||
      !payload.data.as_of?.decision || !payload.data.as_of?.search || !payload.data.as_of?.visitor ||
      typeof payload.data.freshness?.stale !== "boolean") {
    throw new Error("2x2 상태 파일의 구조가 올바르지 않습니다.");
  }
  return payload;
}

export function findReviewMatrixRegion(payload, regionId) {
  return payload?.data?.regions?.find((item) => item.region_id === String(regionId)) ?? null;
}
