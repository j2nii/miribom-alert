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

export default function VisitorProfileCard({ profileData }) {
  const { total_visitors, local_external_mix, residence, distance, spending, companion, profile_tags } =
    profileData;

  return (
    <div>
      <p style={{ fontSize: 14 }}>
        총 방문객 <strong>{total_visitors.toLocaleString()}</strong>명 · 현지 {(local_external_mix.local * 100).toFixed(0)}%
        / 외지 {(local_external_mix.external * 100).toFixed(0)}%
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
