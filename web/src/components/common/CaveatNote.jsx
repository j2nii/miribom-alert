// Renders the envelope's caveat[] -- interpretation caveats (sample limits,
// estimation method, missing-data handling). Never hide this list.
export default function CaveatNote({ envelope }) {
  if (!envelope || !Array.isArray(envelope.caveat) || envelope.caveat.length === 0) {
    return null;
  }

  return (
    <div className="caveat-note">
      <p className="caveat-note__title">해석 시 주의</p>
      <ul>
        {envelope.caveat.map((c, i) => (
          <li key={i}>{c}</li>
        ))}
      </ul>
    </div>
  );
}
