import { runTutor } from '../lib/tauri';

export async function callLearnRpc<T = any>(action: string, params: Record<string, any> = {}): Promise<T> {
  const isTauri = typeof window !== 'undefined' && Boolean((window as any).__TAURI_INTERNALS__);

  // If in browser (outside of Tauri desktop shell), use local dev bridge
  if (!isTauri) {
    // 1. Try relative path via Vite dev proxy
    try {
      const res = await fetch('/api/learn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, params }),
      });
      if (res.ok) {
        return (await res.json()) as T;
      }
      const data = await res.json().catch(() => null);
      if (data) return data as T;
    } catch {
      // Proxy failed or network error, fallback to direct bridge port
    }

    // 2. Direct fallback to bridge port (127.0.0.1:5174)
    try {
      const res2 = await fetch('http://127.0.0.1:5174/api/learn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, params }),
      });
      if (res2.ok) {
        return (await res2.json()) as T;
      }
      const data2 = await res2.json().catch(() => null);
      if (data2) return data2 as T;
      throw new Error(`Server returned HTTP ${res2.status}`);
    } catch (err2: any) {
      console.error('Cannot connect to Preppy backend bridge:', err2);
      throw new Error(err2?.message || 'Preppy bridge is unreachable. Please ensure the Python backend is running.');
    }
  }

  // Inside Tauri desktop environment
  const payload = `[LEARN_RPC:${action}] ${JSON.stringify(params)}`;
  const res = await runTutor(payload);
  const parsed = typeof res === 'string' ? JSON.parse(res) : res;

  if (parsed && parsed.summary) {
    try {
      return JSON.parse(parsed.summary) as T;
    } catch {
      return parsed.summary as unknown as T;
    }
  }
  return parsed as T;
}
