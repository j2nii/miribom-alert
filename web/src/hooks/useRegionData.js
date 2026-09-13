import { useEffect, useState } from "react";
import { loadData } from "../data/loadData.js";

/**
 * React wrapper around loadData(): tracks loading/error/result state and
 * re-fetches whenever region or dataType changes.
 */
export function useRegionData(dataType, region) {
  const [result, setResult] = useState({ status: "loading", region, dataType });

  useEffect(() => {
    let cancelled = false;
    setResult({ status: "loading", region, dataType });

    loadData(dataType, { region }).then((r) => {
      if (!cancelled) setResult(r);
    });

    return () => {
      cancelled = true;
    };
  }, [dataType, region]);

  return result;
}
