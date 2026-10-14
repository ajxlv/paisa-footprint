import { useEffect, useState } from 'react';

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** Run an API call when `key` changes; exposes loading and error states for every page. */
export function useApi<T>(load: () => Promise<T>, key: string = ''): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: true });
  useEffect(() => {
    let cancelled = false;
    setState({ data: null, error: null, loading: true });
    load()
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
