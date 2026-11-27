import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// Hook tải dữ liệu: { data, error, loading, reload }
export default function useApi(path, options) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  const key = JSON.stringify([path, options?.params]);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    api(path, options)
      .then((data) => !cancelled && setState({ data, error: null, loading: false }))
      .catch((error) => !cancelled && setState({ data: null, error, loading: false }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick]);

  return { ...state, reload: () => setTick((t) => t + 1) };
}
