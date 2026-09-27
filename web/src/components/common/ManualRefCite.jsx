// Renders a manual_ref{document,page,section,quote} object -- the device
// that proves a policy action was cited from the manual, not invented by
// the AI. Quote is reproduced verbatim (공공누리 4유형, 변경금지).
export default function ManualRefCite({ manualRef }) {
  if (!manualRef) return null;
  const { document, page, section, quote } = manualRef;

  return (
    <details className="manual-ref-cite compact-details">
      <summary>매뉴얼 근거 · p.{page}</summary>
      <p className="manual-ref-cite__source">
        {document} · p.{page}
        {section ? ` · ${section}` : ""}
      </p>
      {quote ? <blockquote className="manual-ref-cite__quote">“{quote}”</blockquote> : null}
    </details>
  );
}
