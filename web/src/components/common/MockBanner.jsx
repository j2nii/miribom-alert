// Page/region-level banner shown whenever any data on the current screen is
// _mock:true. Distinct from SourceBadge (per-value) -- this is the
// at-a-glance "this whole screen is sample data" signal for the demo.
export default function MockBanner({ isMock }) {
  if (!isMock) return null;

  return (
    <div className="mock-banner" role="status">
      이 화면은 <strong>목업(_mock:true) 데이터</strong> 기준입니다. 실데이터 연동 전까지 수치로 판단하지
      마세요.
    </div>
  );
}
