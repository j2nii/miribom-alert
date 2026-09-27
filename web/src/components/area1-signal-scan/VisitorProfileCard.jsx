function Bar({ label, ratio, color = "var(--teal)" }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginBottom: 4 }}>
      <div style={{ width: 90, flexShrink: 0 }}>{label}</div>
      <div style={{ flex: 1, background: "var(--mist)", borderRadius: 4, height: 10 }}>
        <div
          style={{
            width: `${Math.round(ratio * 100)}%`,
            background: color,
            height: "100%",
            borderRadius: 4,
          }}
        />
      </div>
      <div style={{ width: 42, textAlign: "right" }}>{(ratio * 100).toFixed(1)}%</div>
    </div>
  );
}

export default function VisitorProfileCard({ profileData, spendingLabel = "소비" }) {
  const categories = [
    { label: "거주지", items: profileData.residence, name: (r) => [r.sido, r.sigungu].filter(Boolean).join(" ") },
    { label: "이동 거리", items: profileData.distance, name: (r) => r.band },
    { label: spendingLabel, items: profileData.spending, name: (r) => r.category },
    { label: "동행 유형", items: profileData.companion, name: (r) => r.type },
  ];
  return <div>
    <p className="profile-total">총 방문객 <strong>{Number.isFinite(profileData.total_visitors) ? profileData.total_visitors.toLocaleString("ko-KR") : "—"}</strong>명</p>
    <div className="profile-highlights">
      {categories.map(({ label, items = [], name }) => {
        const ranked = items.filter((item) => Number.isFinite(item.ratio)).slice().sort((a, b) => b.ratio - a.ratio);
        const top = ranked[0];
        const tied = top ? ranked.filter((item) => item.ratio === top.ratio).length : 0;
        return <div className="profile-highlight" key={label}>
          <span>{label} {top ? (tied > 1 ? "공동 1위" : "1위") : ""}</span>
          <strong>{top ? name(top) : "자료 없음"}</strong>
          {top && <small>{(top.ratio * 100).toFixed(1)}%{tied > 1 ? ` · 외 ${tied - 1}곳 동일 비중` : ""}</small>}
        </div>;
      })}
    </div>
    <details className="compact-details"><summary>방문객 구성 전체 보기</summary><ProfileDetails profileData={profileData} /></details>
  </div>;
}

function ProfileDetails({ profileData }) {
  const { total_visitors, local_external_mix, residence, distance, spending, companion, profile_tags } =
    profileData;

  return (
    <div>
      <p style={{ fontSize: 14 }}>
        총 방문객 <strong>{total_visitors.toLocaleString()}</strong>명
        {local_external_mix && (
          <>
            {" "}
            · 현지 {(local_external_mix.local * 100).toFixed(0)}% / 외지{" "}
            {(local_external_mix.external * 100).toFixed(0)}%
          </>
        )}
      </p>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
        {profile_tags.map((t) => (
          <span
            key={t}
            style={{
              fontSize: 11,
              padding: "2px 8px",
              borderRadius: 999,
              background: "#e1efe8",
              color: "var(--teal)",
            }}
          >
            {t}
          </span>
        ))}
      </div>

      <p style={{ fontSize: 13, fontWeight: 700, margin: "10px 0 4px" }}>거주지 상위</p>
      {residence.slice(0, 5).map((r, i) => (
        <Bar key={i} label={`${r.sido}${r.sigungu ? " " + r.sigungu : ""}`} ratio={r.ratio} />
      ))}

      <p style={{ fontSize: 13, fontWeight: 700, margin: "10px 0 4px" }}>거리대별</p>
      {distance.map((d, i) => (
        <Bar key={i} label={d.band} ratio={d.ratio} color="var(--amber)" />
      ))}

      <p style={{ fontSize: 13, fontWeight: 700, margin: "10px 0 4px" }}>소비 카테고리</p>
      {spending.map((s, i) => (
        <Bar key={i} label={s.category} ratio={s.ratio} color="#8858c8" />
      ))}

      <p style={{ fontSize: 13, fontWeight: 700, margin: "10px 0 4px" }}>동행 유형</p>
      {companion.map((c, i) => (
        <Bar key={i} label={c.type} ratio={c.ratio} color="var(--crimson)" />
      ))}
    </div>
  );
}
