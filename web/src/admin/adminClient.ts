/**
 * Transport for the local review tool (planning.md 16.3).
 *
 * No auth header, because there is no auth: the server binds 127.0.0.1 and the
 * safest gate is nothing exposed (16.1). Vite proxies `/api/admin` to it, so
 * this is same-origin and CORS never enters the picture.
 */

export interface QueuePuzzle {
  hash: string;
  start: string;
  end: string;
  solution: string[];
  /** start + solution + end — six words, so five links between them. */
  chain: string[];
  decoys: string[];
  bank: string[];
  quality: number | null;
  /** One per link; `chain[i] -> chain[i+1]` has weight `linkWeights[i]`. */
  linkWeights: number[];
  relations: string[][];
}

export interface QueueCounts {
  total: number;
  pending: number;
  approved: number;
  scheduled: number;
  rejected: number;
}

export interface QueueResponse {
  puzzles: QueuePuzzle[];
  counts: QueueCounts;
}

/** The server puts its reason in `error`; showing it beats a status code. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new Error('Cannot reach the admin server. Is `linkage admin` running?');
  }

  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const message =
      typeof body === 'object' && body !== null && typeof (body as { error?: unknown }).error === 'string'
        ? (body as { error: string }).error
        : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return body as T;
}

const post = <T,>(path: string, payload: object): Promise<T> =>
  request<T>(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });

export const fetchQueue = (): Promise<QueueResponse> => request('/api/admin/queue');

export const approvePuzzle = (hash: string): Promise<unknown> =>
  post('/api/admin/approve', { hash });

/** `badLink` indexes `chain` links, 0..4. Optional, and far more useful than prose. */
export const rejectPuzzle = (
  hash: string,
  reason: string,
  badLink: number | null,
): Promise<unknown> => post('/api/admin/reject', { hash, reason, badLink });

export const undoPuzzle = (hash: string): Promise<unknown> => post('/api/admin/undo', { hash });
