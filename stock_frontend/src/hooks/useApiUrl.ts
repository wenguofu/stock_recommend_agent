import { useMemo } from 'react';

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:35000';

/**
 * Resolve the backend API base URL from Vite env, with a localhost fallback
 * for local dev. Memoized so it's referentially stable across renders.
 */
export function useApiUrl(): string {
  return useMemo(
    () => (import.meta as any).env?.VITE_API_BASE_URL || DEFAULT_API_BASE_URL,
    []
  );
}
