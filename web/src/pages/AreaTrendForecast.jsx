import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import ForecastChart from "../components/area1-signal-scan/ForecastChart.jsx";
import { alignedSignalSeries } from "../lib/alignedSignalSeries.js";

export default function AreaTrendForecast({ region }) {
  const forecast = useRegionData("forecast", region);
  const signalSeries = useRegionData("signal_series", region);
  const observedDaily = signalSeries.status === "ok" ? alignedSignalSeries(signalSeries.envelope.data).daily : [];

  return <section className="section-block trend-daily-forecast" id="forecast" aria-labelledby="forecast-title">
    <div className="regional-section-head">
      <div><span className="regional-step">04 · 이후</span><h3 id="forecast-title">7일 방문 예측</h3></div>
      <p>자료 기준일 이후 7일의 예상 방문을 살펴봅니다.</p>
    </div>
    <DataState result={forecast} render={({ envelope }) => <>
      <ForecastChart forecastData={envelope.data} period={envelope.period} observedDaily={observedDaily} />
      <div className="forecast-sources">
        {signalSeries.status === "ok" && <SourceBadge envelope={signalSeries.envelope} label="실측" />}
        <SourceBadge envelope={envelope} label={envelope._mock ? "샘플 예측" : "예측"} />
      </div>
    </>} />
  </section>;
}
