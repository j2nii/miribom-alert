// Keep the original caveats available without expanding every explanation by default.
export default function CaveatNote({ envelope }) {
  if (!envelope || !Array.isArray(envelope.caveat) || envelope.caveat.length === 0) {
    return null;
  }

  return (
    <details className="caveat-note compact-details">
      <summary>데이터 유의사항 · {envelope.caveat.length}건</summary>
      <ul>
        {envelope.caveat.map((c, i) => (
          <li key={i}>{c}</li>
        ))}
      </ul>
    </details>
  );
}
