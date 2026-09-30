import Term from "../common/Term.jsx";

export default function HotspotRanking({ hotspotsData, deadZonePois = [] }) {
  const ranking = [...(hotspotsData.ranking ?? [])].sort((a, b) => a.rank - b.rank);
  return <ul className="rank-list analysis-hotspot-list" aria-label="관광지 순위">
    {ranking.map((poi) => {
      const isDeadZone = deadZonePois.includes(poi.poi_name);
      return <li key={poi.rank} className="rank-row">
        <span className="rank-index">{poi.rank}</span>
        <div className="analysis-hotspot-main">
          <div className="analysis-hotspot-head">
            <strong>{poi.poi_name}{isDeadZone && <span className="dept-chip"><Term name="분산 후보지">분산 후보지</Term></span>}</strong>
            <span className={poi.change_rate >= 0 ? "is-up" : "is-down"}>
              {poi.change_rate >= 0 ? "+" : ""}{(poi.change_rate * 100).toFixed(1)}%
            </span>
          </div>
          <p className="analysis-hotspot-meta">
            {poi.visitors.toLocaleString()}명{poi.congestion_level != null && ` · 혼잡도 ${poi.congestion_level}/5`} · {poi.spatial_type}
          </p>
          {poi.bottleneck && <p className="analysis-hotspot-meta">
            병목: {poi.bottleneck.name} (체류 {poi.bottleneck.dwell_minutes}분, 이동속도 {poi.bottleneck.avg_speed_mps}m/s)
          </p>}
        </div>
      </li>;
    })}
  </ul>;
}
