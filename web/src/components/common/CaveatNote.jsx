// Renders the envelope's caveat[] -- interpretation caveats (sample limits,
// estimation method, missing-data handling).
//
// 기본 접힘(<details>)이지만 "해석 시 주의 N건"이라는 제목과 건수는 접힌 상태에서도 항상
// 보인다. 즉 주의 사항이 있다는 사실 자체는 결코 숨기지 않으면서(_envelope.schema.json의
// "출처 없는 값은 표시되지 않는다" 원칙 유지), 첫 화면의 정보 밀도만 낮춘다 -- AREA0에
// 들어오자마자 게이지보다 caveat 목록이 더 큰 면적을 차지했다는 QA 피드백 반영.
export default function CaveatNote({ envelope }) {
  if (!envelope || !Array.isArray(envelope.caveat) || envelope.caveat.length === 0) {
    return null;
  }

  return (
    <details className="caveat-note">
      <summary className="caveat-note__title">해석 시 주의 {envelope.caveat.length}건</summary>
      <ul>
        {envelope.caveat.map((c, i) => (
          <li key={i}>{c}</li>
        ))}
      </ul>
    </details>
  );
}
