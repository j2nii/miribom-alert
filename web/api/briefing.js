import OpenAI from "openai";

// Vercel serverless function (Node runtime). "AI 정책 초안 도우미" -- now
// calling Upstage Solar instead of Claude, per request. Upstage advertises
// an OpenAI-compatible Chat Completions endpoint, so this uses the `openai`
// SDK pointed at Upstage's base URL rather than a bespoke HTTP client.
//
// base_url and model confirmed from the exact snippet shown on the user's
// own Upstage console API-key page (solar-pro4, https://api.upstage.ai/v1).
const client = new OpenAI({
  apiKey: process.env.UPSTAGE_API_KEY,
  baseURL: "https://api.upstage.ai/v1",
});

const MODEL = process.env.UPSTAGE_MODEL || "solar-pro4";

const SYSTEM_PROMPT = `당신은 지자체 관광 담당 공무원을 위한 정책 브리핑 초안을 작성합니다.
반드시 아래 규칙을 지키세요 (docs/설계결정.md D-04):
- 정확히 3문단: 1) 상황 2) 전개(전망) 3) 조치
- 전체 길이는 400~600자 (공백 포함)
- 조치는 최대 3개까지만 제시하고, 각 조치 끝에 "(매뉴얼 p.N)" 형식으로 근거 페이지를 반드시 표기한다. 입력된 checklist 항목에 없는 조치는 절대 만들어내지 않는다.
- 입력에 없는 수치를 만들어내지 않는다. 예측 수치는 항상 lower~upper 구간과 함께 언급한다.
- "AI가 분석한", "AI 판단으로는" 등 자기 자신을 언급하는 표현을 쓰지 않는다.
- 확정적인 단정 대신 예측·전망 표현을 쓴다.
- 문단 사이는 빈 줄로 구분한다.`;

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "POST only" });
    return;
  }

  if (!process.env.UPSTAGE_API_KEY) {
    res.status(503).json({ error: "UPSTAGE_API_KEY not configured on server" });
    return;
  }

  const { region, regionLabel, signalStatus, forecast, checklist } = req.body ?? {};
  if (!signalStatus) {
    res.status(400).json({ error: "signalStatus is required" });
    return;
  }

  const facts = { region, regionLabel, signalStatus, forecast, checklist };

  try {
    const completion = await client.chat.completions.create({
      model: MODEL,
      max_tokens: 1024,
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        {
          role: "user",
          content: `다음은 이미 계산·매칭이 끝난 사실 데이터다. 이 데이터에만 근거해 브리핑을 작성하라.\n\n${JSON.stringify(facts, null, 2)}`,
        },
      ],
    });

    const text = completion.choices?.[0]?.message?.content?.trim();

    if (!text) {
      res.status(502).json({ error: "empty response from model" });
      return;
    }

    res.status(200).json({
      text,
      paragraphs: text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean),
      charCount: text.length,
    });
  } catch (err) {
    const status = err?.status ?? 500;
    res.status(status).json({ error: err?.message ?? String(err) });
  }
}
