export default function HotspotRanking({ hotspotsData, deadZonePois = [] }) {
  return (
    <ul className="rank-list">
      {hotspotsData.ranking.map((poi) => {
        const isDeadZone = deadZonePois.includes(poi.poi_name);
        return (
          <li key={poi.rank} className="rank-row" style={{ alignItems: "flex-start" }}>
            <span className="rank-index">{poi.rank}</span>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span style={{ fontWeight: 700 }}>
                  {poi.poi_name}
                  {isDeadZone && (
                    <span className="dept-chip" style={{ marginLeft: 6 }}>
                      분산 후보지
                    </span>
                  )}
                </span>
                <span style={{ color: poi.change_rate >= 0 ? "var(--crimson)" : "var(--teal)", fontWeight: 700 }}>
                  {poi.change_rate >= 0 ? "+" : ""}
                  {(poi.change_rate * 100).toFixed(1)}%
                </span>
              </div>
              <div style={{ color: "var(--ink-soft)", fontSize: 11 }}>
                {poi.visitors.toLocaleString()}명 · 혼잡도 {poi.congestion_level}/5 · {poi.spatial_type}
              </div>
              {poi.bottleneck && (
                <div style={{ color: "var(--ink-soft)", fontSize: 11 }}>
                  병목: {poi.bottleneck.name} (체류 {poi.bottleneck.dwell_minutes}분, 이동속도{" "}
                  {poi.bottleneck.avg_speed_mps}m/s)
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
