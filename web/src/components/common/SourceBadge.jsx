import Term from "./Term.jsx";

// Renders the envelope's _mock flag + source[] list, reusing the reference
// demo's own real/sample tag language (source-tag-real / source-tag-sample)
// -- "출처 없는 값은 표시되지 않는다" (data/schema/_envelope.schema.json).
export default function SourceBadge({ envelope, label }) {
  if (!envelope) return null;
  const { _mock, source = [] } = envelope;
  // 호출처가 라벨을 주면 그걸 쓴다 -- 같은 봉투라도 '예측'처럼 자료 성격을 밝혀야 할 때가 있다.
  const badgeLabel = label ?? (_mock ? "샘플" : "실측");
  const tag = <span className={_mock ? "source-tag-sample" : "source-tag-real"}>{badgeLabel}</span>;

  return (
    <div className="source-badge">
      {/* 기본 라벨일 때만 용어 풀이를 붙인다 -- '예측' 같은 라벨에 '실측' 설명은 맞지 않는다. */}
      {label ? tag : <Term name="실측">{tag}</Term>}
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
