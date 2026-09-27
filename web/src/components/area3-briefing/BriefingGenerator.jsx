import { timestampForFilename, downloadTextFile } from "../../lib/format.js";

// Displays agent5_briefing.py's pre-generated data/prod/briefing.json --
// no live LLM call here. A previous version of this component called
// /api/briefing.js on a button click to draft a fresh 3-paragraph briefing
// with Upstage every time -- that duplicated agent5's role and, worse,
// contradicted D-04 ("매일 같은 문장 틀이어야 어제와 비교된다"): a live
// free-form regeneration can't guarantee the same wording/structure run to
// run, while agent5's code+LLM hybrid (code writes paragraphs 1-2 from a
// fixed template, LLM only writes paragraph 3's synthesis + action picks)
// does. If real-time regeneration is ever wanted, it should re-run
// agent5_briefing.py itself with fresh inputs, not a second bespoke LLM call
// outside that pipeline.
export default function BriefingGenerator({ briefingData, regionLabel }) {
  const text = briefingData.paragraphs.map((p) => `[${p.heading}]\n${p.text}`).join("\n\n");

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
  };

  const handleDownload = () => {
    downloadTextFile(`정책브리핑_${regionLabel}_${timestampForFilename()}.txt`, text);
  };

  return (
    <div>
      <p className="section-title">정책 브리핑 (agent5_briefing.py)</p>

      {briefingData.paragraphs.map((p, i) => (
        <div key={i} style={{ marginBottom: 8 }}>
          <p className="subsection-title" style={{ color: "var(--ink-soft)" }}>{p.heading}</p>
          <p style={{ fontSize: 13, whiteSpace: "pre-wrap", margin: "2px 0 0" }}>{p.text}</p>
        </div>
      ))}

      <p style={{ fontSize: 11, color: "var(--ink-soft)" }}>
        글자 수 {briefingData.char_count}자 (목표 400~600자) · 기준일 {briefingData.as_of}
      </p>

      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={handleCopy} className="btn-ghost">
          복사
        </button>
        <button onClick={handleDownload} className="btn-ghost">
          파일로 저장
        </button>
      </div>
    </div>
  );
}
