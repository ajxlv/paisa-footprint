import { useEffect, useRef, useState } from 'react';

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** Run an API call when `key` changes; exposes loading and error states for every page. */
export function useApi<T>(load: () => Promise<T>, key: string = ''): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: true });
  // Callers pass inline functions; keep the latest one in a ref so the effect re-runs on `key`
  // changes only, not on every render.
  const loadRef = useRef(load);
  loadRef.current = load;
  useEffect(() => {
    let cancelled = false;
    setState({ data: null, error: null, loading: true });
    loadRef.current()
      .then((data) => !cancelled && setState({ data, error: null, loading: false }))
      .catch((err: unknown) =>
        !cancelled &&
        setState({ data: null, error: err instanceof Error ? err.message : String(err), loading: false }),
      );
    return () => {
      cancelled = true;
    };
  }, [key]);
  return state;
}
