export async function runTutor(payload: string): Promise<any> {
  const isTauri = typeof window !== 'undefined' && Boolean((window as any).__TAURI_INTERNALS__);
  if (!isTauri) return null;
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    return await invoke('run_tutor', { payload });
  } catch {
    return null;
  }
}
