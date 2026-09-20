import { useState } from "react";
import { generateBriefing } from "../../lib/briefingTemplate.js";
import { timestampForFilename, downloadTextFile } from "../../lib/format.js";

// Calls the server-side /api/briefing function (Claude), restoring the
// original "AI 정책 초안 도우미" concept -- unlike the old demo, the API key
// stays server-side (Vercel env var), never shipped to the browser. If the
// call fails (no key configured yet, network error, rate limit), falls back
// to the local rule-based generator so the demo still produces something.
export default function BriefingGenerator({ signalStatus, forecast, checklist, region, regionLabel }) {
  const [briefing, setBriefing] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [fellBack, setFellBack] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    setCopied(false);
    setFellBack(false);

    try {
      const res = await fetch("/api/briefing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          region,
          regionLabel,
          signalStatus: signalStatus.data,
          forecast: forecast?.data ?? null,
          checklist: checklist?.data ?? null,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setBriefing({ paragraphs: data.paragraphs, text: data.text, charCount: data.charCount });
    } catch (err) {
      // LLM call unavailable (e.g. ANTHROPIC_API_KEY not set in this
      // environment) -- fall back to the deterministic template so the demo
      // still works, but flag that it's not the LLM-generated version.
      const fallback = generateBriefing({ signalStatus, forecast, checklist, region });
      setBriefing(fallback);
      setFellBack(true);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!briefing) return;
    await navigator.clipboard.writeText(briefing.text);
    setCopied(true);
  };

  const handleDownload = () => {
    if (!briefing) return;
    downloadTextFile(`정책브리핑_${regionLabel}_${timestampForFilename()}.txt`, briefing.text);
  };

  return (
    <div>
      <p className="section-title">AI 정책 초안 도우미</p>
      <button onClick={handleGenerate} disabled={loading} className="btn-primary">
        {loading ? "생성 중…" : "브리핑 생성"}
      </button>

      {briefing && (
        <div style={{ marginTop: 12 }}>
          {fellBack && (
            <p style={{ fontSize: 11, color: "var(--amber-tint-text)", margin: "0 0 6px" }}>
              LLM 호출에 실패해 규칙 기반 생성으로 대체되었습니다 (서버에 UPSTAGE_API_KEY가 설정되어 있는지
              확인하세요).
            </p>
          )}
          {briefing.paragraphs.map((p, i) => (
            <p key={i} style={{ fontSize: 13, whiteSpace: "pre-wrap" }}>
              {p}
            </p>
          ))}
          <p style={{ fontSize: 11, color: "var(--ink-soft)" }}>
            글자 수 {briefing.charCount}자 (목표 400~600자)
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={handleCopy} className="btn-ghost">
              {copied ? "복사됨" : "복사"}
            </button>
            <button onClick={handleDownload} className="btn-ghost">
              파일로 저장
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
