import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { reviewMatrixPresentation } from "./presentation.js";
import { findReviewMatrixRegion, loadReviewMatrix } from "../../data/loadReviewMatrix.js";

const payload = JSON.parse(fs.readFileSync(new URL("../../../../data/prod/review_matrix_latest.json", import.meta.url), "utf8"));

test("selected five-digit region IDs resolve to the supplied regional records", () => {
  for (const [id, name] of [["51750", "영월군"], ["48310", "거제시"], ["43130", "충주시"]]) {
    assert.equal(findReviewMatrixRegion(payload, id).region_name, name);
  }
  assert.equal(findReviewMatrixRegion(payload, undefined), null);
  assert.equal(findReviewMatrixRegion(payload, "00000"), null);
});

test("stale data stays latest-available and alert language stays provisional", () => {
  const online = reviewMatrixPresentation("online_watch", { stale: true });
  assert.equal(online.freshnessLabel, "최신 가용 데이터 기준");
  assert.equal(online.label, "온라인 관심 후보");
  assert.match(online.interpretation, /확정.*아닙니다/);
  const combined = reviewMatrixPresentation("combined_alert", { stale: true });
  assert.equal(combined.label, "우선 검토 필요");
  assert.match(combined.interpretation, /인과관계가 확인된 것은 아닙니다/);
});

test("loader uses production matrix and rejects incomplete payloads", async (t) => {
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "/prod/review_matrix_latest.json");
    assert.equal(options.cache, "no-store");
    return { ok: true, json: async () => payload };
  });
  assert.equal(await loadReviewMatrix(), payload);
  globalThis.fetch.mock.mockImplementation(async () => ({ ok: true, json: async () => ({ data: { regions: [], summary: {} } }) }));
  await assert.rejects(loadReviewMatrix(), /구조/);
});
