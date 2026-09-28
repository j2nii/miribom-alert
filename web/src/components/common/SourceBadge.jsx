// Renders the envelope's _mock flag + source[] list, reusing the reference
// demo's own real/sample tag language (source-tag-real / source-tag-sample)
// -- "출처 없는 값은 표시되지 않는다" (data/schema/_envelope.schema.json).
export default function SourceBadge({ envelope, label }) {
  if (!envelope) return null;
  const { _mock, source = [] } = envelope;

  return (
    <div className="source-badge">
      <span className={_mock ? "source-tag-sample" : "source-tag-real"}>
        {label ?? (_mock ? "샘플" : "실측")}
      </span>
      <details className="source-badge__details">
        <summary>출처 {source.length}건</summary>
        <ul>
          {source.map((s, i) => (
            <li key={i}>
              <strong>{s.name}</strong> · {s.provider} ({s.retrieved_at})
              {s.note ? <span className="source-badge__note"> — {s.note}</span> : null}
              {s.url ? (
                <>
                  {" "}
                  <a href={s.url} target="_blank" rel="noreferrer">
                    링크
                  </a>
                </>
              ) : null}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
