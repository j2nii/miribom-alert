// Renders a manual_ref{document,page,section,quote} object -- the device
// that proves a policy action was cited from the manual, not invented by
// the AI. Quote is reproduced verbatim (공공누리 4유형, 변경금지).
export default function ManualRefCite({ manualRef, alwaysVisible = false }) {
  if (!manualRef) return null;
  const { document, page, section, quote } = manualRef;
  const source = <p className="manual-ref-cite__source">
    {document} · p.{page}
    {section ? ` · ${section}` : ""}
  </p>;
  const citation = quote ? <blockquote className="manual-ref-cite__quote">“{quote}”</blockquote> : null;

  // 원문 인용이 이 컴포넌트의 존재 이유다(조치가 매뉴얼에서 나왔다는 증거).
  // alwaysVisible이라고 quote를 빼면 출처 줄만 남아 근거 역할을 못 한다.
  if (alwaysVisible) return <div className="manual-ref-cite manual-ref-cite--visible">
    <strong>매뉴얼 근거</strong>
    {source}
    {citation}
  </div>;

  return (
    <details className="manual-ref-cite compact-details">
      <summary>매뉴얼 근거 · p.{page}</summary>
      {source}
      {citation}
    </details>
  );
}
