import OpenAI from "openai";
import { getManifestEntry } from "./_lib/dataManifest.js";

// Vercel serverless function (Node runtime). "자연어 질의 인터페이스" -- lets a
// 공무원 ask a free-form question and get an answer grounded in the same 9
// JSON data contracts the rest of the app reads (see docs/meeting-notes/UI/
// 자연어_질의_인터페이스_구현계획.md). Uses real OpenAI-compatible tool-calling
// (confirmed supported by Upstage Solar Pro 4) instead of a vector-search
// RAG pipeline -- the corpus is 9 small, already-structured JSON files, not
// a large unstructured text corpus, so "which files are relevant" is a job
// for tool-calling, not embeddings.
//
// Response is streamed as newline-delimited JSON (one `{type, ...}` object
// per line) instead of one JSON blob at the end, so the browser can render
// tokens as they arrive: {type:"token", text} while the model is writing
// the final answer, then one {type:"done", usedDataTypes, envelopes} once
// it's finished (or {type:"error", error} if something failed).
const client = new OpenAI({
  apiKey: process.env.UPSTAGE_API_KEY,
  baseURL: "https://api.upstage.ai/v1",
});

const MODEL = process.env.UPSTAGE_MODEL || "solar-pro4";

// One tool per data contract. No parameters -- region is fixed server-side
// from the request body so the model can't fabricate answers for a region
// it wasn't asked about.
const TOOLS = [
  { name: "get_signal_status", dataType: "signal_status", description: "현재 경보 단계와 3중 교차검증(관심·의도·실현) 판정 결과" },
  { name: "get_forecast", dataType: "forecast", description: "향후 90일 방문자 예측과 요일별 집중률" },
  { name: "get_visitor_profile", dataType: "visitor_profile", description: "방문객 성/연령, 거주지, 이동 거리, 소비 성향, 동반 유형 분포" },
  { name: "get_hotspots", dataType: "hotspots", description: "급증 지점 랭킹 (현지인/외지인 구분)" },
  { name: "get_content_type", dataType: "content_type", description: "SNS·유튜브 콘텐츠 유형 분류 결과 (핫존·데드존 신호 포함)" },
  { name: "get_checklist", dataType: "checklist", description: "현재 상황에 매칭된 혼잡도 운영관리 매뉴얼 체크리스트" },
  { name: "get_precedent", dataType: "precedent", description: "유사 지역의 과거 대응 선례" },
  { name: "compare_before_after", dataType: "before_after", description: "조치 시행 전후 방문자·소비·체류시간 변화 비교" },
  { name: "get_timeline", dataType: "timeline", description: "바이럴 확산부터 행정 대응까지의 사례별 타임라인" },
];
const TOOL_BY_NAME = Object.fromEntries(TOOLS.map((t) => [t.name, t]));

const ANSWER_RULES = `당신은 지자체 관광 담당 공무원의 질문에 답하는 도우미입니다.
- 제공된 데이터(JSON)에 있는 사실에만 근거해 답하세요. 없는 수치·조치를 지어내지 마세요.
- 수치를 말할 때는 어떤 데이터에 근거했는지 드러나게 답하고, caveat가 있으면 함께 언급하세요.
- 데이터가 "unsupported"(준비 전)이면 그 사실을 정직하게 답하세요.
- 공무원에게 보고하듯 간결한 문어체로, 2~4문장 이내로 답하세요.
- "AI가 분석한" 같은 자기 언급 표현은 쓰지 마세요.`;

function buildToolSpecs() {
  return TOOLS.map((t) => ({
    type: "function",
    function: {
      name: t.name,
      description: t.description,
      parameters: { type: "object", properties: {}, additionalProperties: false },
    },
  }));
}

function baseUrl(req) {
  const host = req.headers["x-forwarded-host"] ?? req.headers.host;
  // Vercel sets x-forwarded-proto on every proxied request in production.
  // When it's absent (e.g. `vercel dev`/a local proxy that doesn't set it),
  // guess from the host instead of defaulting to https -- a plain http
  // localhost server will otherwise fail the fetch below with a silent
  // TLS/connection error.
  const proto = req.headers["x-forwarded-proto"] ?? (/^(localhost|127\.0\.0\.1)(:|$)/.test(host ?? "") ? "http" : "https");
  return `${proto}://${host}`;
}

// Fetches the same static envelope file the browser's loadData.js reads --
// no separate data-loading logic, just a server-side caller of the same URL.
async function fetchEnvelope(req, region, dataType) {
  const entry = getManifestEntry(region, dataType);
  if (!entry) return { dataType, status: "unsupported" };

  try {
    const r = await fetch(`${baseUrl(req)}${entry.url}`);
    if (!r.ok) return { dataType, status: "error", error: `HTTP ${r.status}` };
    return { dataType, status: "ok", kind: entry.kind, envelope: await r.json() };
  } catch (err) {
    return { dataType, status: "error", error: String(err) };
  }
}

function writeLine(res, obj) {
  res.write(JSON.stringify(obj) + "\n");
}

// Streams the model's reply straight to the client as {type:"token"} lines
// instead of waiting for the full completion. `state.started` flips true on
// the first token written, so the caller knows a partial answer is already
// on the wire and must not fall back to a second, independent answer.
async function streamAnswer(res, messages, state) {
  const stream = await client.chat.completions.create({ model: MODEL, max_tokens: 1024, messages, stream: true });
  let full = "";
  for await (const chunk of stream) {
    const delta = chunk.choices?.[0]?.delta?.content;
    if (delta) {
      state.started = true;
      full += delta;
      writeLine(res, { type: "token", text: delta });
    }
  }
  return full.trim();
}

// Primary path: let the model pick which of the 9 tools it needs, run
// exactly those, then stream the answer from the results.
async function answerWithToolCalling(req, res, region, baseMessages, state) {
  const messages = [...baseMessages];
  const usedDataTypes = [];
  const envelopes = {};

  const first = await client.chat.completions.create({
    model: MODEL,
    max_tokens: 1024,
    messages,
    tools: buildToolSpecs(),
    tool_choice: "auto",
    parallel_tool_calls: true,
  });

  const firstMessage = first.choices?.[0]?.message;
  const toolCalls = firstMessage?.tool_calls ?? [];

  if (toolCalls.length === 0) {
    const text = firstMessage?.content?.trim();
    if (text) {
      state.started = true;
      writeLine(res, { type: "token", text });
    }
    return { answer: text, usedDataTypes, envelopes };
  }

  messages.push(firstMessage);

  for (const call of toolCalls) {
    const tool = TOOL_BY_NAME[call.function?.name];
    const result = tool
      ? await fetchEnvelope(req, region, tool.dataType)
      : { dataType: call.function?.name, status: "error", error: "unknown tool" };

    usedDataTypes.push(result.dataType);
    if (result.status === "ok") envelopes[result.dataType] = result.envelope;

    messages.push({ role: "tool", tool_call_id: call.id, content: JSON.stringify(result) });
  }

  const answer = await streamAnswer(res, messages, state);
  return { answer, usedDataTypes, envelopes };
}

// Safety net: if tool-calling itself errors out (network hiccup, unexpected
// response shape) *before* anything was streamed, fetch all 9 contracts
// directly and answer from a single call. The files are small, so stuffing
// all of them is cheap and reliable.
async function answerWithAllData(req, res, region, baseMessages, state) {
  const results = await Promise.all(TOOLS.map((t) => fetchEnvelope(req, region, t.dataType)));
  const envelopes = {};
  const usedDataTypes = results.map((r) => {
    if (r.status === "ok") envelopes[r.dataType] = r.envelope;
    return r.dataType;
  });

  const messages = [
    ...baseMessages,
    { role: "user", content: `참고 데이터(JSON):\n${JSON.stringify(results, null, 2)}` },
  ];
  const answer = await streamAnswer(res, messages, state);
  return { answer, usedDataTypes, envelopes };
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "POST only" });
    return;
  }
  if (!process.env.UPSTAGE_API_KEY) {
    res.status(503).json({ error: "UPSTAGE_API_KEY not configured on server" });
    return;
  }

  const { region, regionLabel, question, history } = req.body ?? {};
  if (!region || !question) {
    res.status(400).json({ error: "region and question are required" });
    return;
  }

  const trimmedHistory = Array.isArray(history) ? history.slice(-6) : [];
  const baseMessages = [
    { role: "system", content: ANSWER_RULES },
    { role: "system", content: `현재 조회 지역: ${regionLabel ?? region} (${region})` },
    ...trimmedHistory,
    { role: "user", content: question },
  ];

  // Streamed as newline-delimited JSON from here on -- once headers are
  // sent we can no longer send a plain error status, so every failure past
  // this point is reported as a {type:"error"} line instead.
  res.writeHead(200, { "Content-Type": "application/x-ndjson; charset=utf-8", "Cache-Control": "no-cache" });

  const state = { started: false };
  try {
    let result;
    try {
      result = await answerWithToolCalling(req, res, region, baseMessages, state);
    } catch (err) {
      if (state.started) throw err; // a partial answer is already on the wire -- don't also send a second one
      result = await answerWithAllData(req, res, region, baseMessages, state);
    }

    if (!result.answer) {
      writeLine(res, { type: "error", error: "empty response from model" });
    } else {
      writeLine(res, { type: "done", usedDataTypes: result.usedDataTypes, envelopes: result.envelopes });
    }
  } catch (err) {
    writeLine(res, { type: "error", error: err?.message ?? String(err) });
  } finally {
    res.end();
  }
}
