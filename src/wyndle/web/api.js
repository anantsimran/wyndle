// Transport is kept separate so future clients can reuse the same action contract.
export async function request(action, data = {}) {
  const response = await fetch(action ? '/api/action' : '/api/status', action ? {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Wyndle-Client': 'dashboard' },
    body: JSON.stringify({ action, data }),
    signal: AbortSignal.timeout(10000),
  } : { cache: 'no-store', signal: AbortSignal.timeout(10000) });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Something went wrong. Please try again.');
  return body;
}

export function duration(seconds) {
  const minutes = Math.floor(Math.max(0, seconds) / 60);
  return minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m`;
}
