import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { summarizeSignals, selectRegionalVideos } from "./regionSummary.js";

function fixture(file) {
  return JSON.parse(readFileSync(new URL(`../../../${file}`, import.meta.url), "utf8"));
}

test("Yeongwol describes search activity without claiming actual visitor growth", () => {
  const signal = fixture("data/prod/signal_status_51750.json");
  assert.match(summarizeSignals(signal.data).headline, /검색/);
  assert.match(summarizeSignals(signal.data).description, /별도로 확인/);
});

test("high-view unrelated videos are excluded from the regional issue summary", () => {
  const content = fixture("data/prod/content_type_51750.json");
  const original = JSON.stringify(content);
  const selected = selectRegionalVideos(content);
  assert.equal(selected.length, 2);
  assert.equal(selected[0].video_id, "nxukV1yfvCA");
  assert.ok(selected.every((item) => item.content_type !== "관광무관" && item.confidence >= 0.6));
  assert.equal(JSON.stringify(content), original);
});

test("sample lifecycle data does not become an operational warning", () => {
  const signal = fixture("data/mock/chungju_signal_status.json");
  assert.match(summarizeSignals(signal.data).description, /예시 데이터/);
  assert.match(summarizeSignals(signal.data).headline, /참고 사례/);
});

test("missing and uncertain content is not promoted as a regional issue", () => {
  assert.deepEqual(selectRegionalVideos(null), []);
  assert.deepEqual(selectRegionalVideos({ data: { items: [
    { title: "불확실한 영상", content_type: "맛집형", confidence: 0.59, view_count: 999999 },
    { title: "신뢰도 미제공", content_type: "맛집형" },
  ] } }), []);
});
