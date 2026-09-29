// Keep source details available while omitting the redundant "실측" tag.
// Sample and forecast labels remain visible where they clarify the data type.
export default function SourceBadge({ envelope, label }) {
  if (!envelope) return null;
  const { _mock, source = [] } = envelope;
  const badgeLabel = label ?? (_mock ? "샘플" : "실측");

  return (
    <div className="source-badge">
      {badgeLabel !== "실측" && <span className={_mock ? "source-tag-sample" : "source-tag-real"}>{badgeLabel}</span>}
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
