import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import ForecastChart from "../components/area1-signal-scan/ForecastChart.jsx";

export default function AreaTrendForecast({ region }) {
  const forecast = useRegionData("forecast", region);

  return <section className="section-block trend-daily-forecast" id="forecast" aria-labelledby="forecast-title">
    <div className="regional-section-head">
      <div><span className="regional-step">04 · 이후</span><h3 id="forecast-title">앞으로 7일 방문 예측</h3></div>
      <p>실측 방문 흐름을 바탕으로 다음 7일을 살펴봅니다.</p>
    </div>
    <DataState result={forecast} render={({ envelope }) => <>
      <ForecastChart forecastData={envelope.data} period={envelope.period} />
      <SourceBadge envelope={envelope} label={envelope._mock ? "샘플 예측" : "예측"} />
    </>} />
  </section>;
}
