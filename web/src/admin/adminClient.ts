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

/** `edits` carries any hand swaps; the server re-proves them before storing. */
export const approvePuzzle = (hash: string, edits: BankEdit[] = []): Promise<unknown> =>
  post('/api/admin/approve', edits.length > 0 ? { hash, edits } : { hash });

/** `badLink` indexes `chain` links, 0..4. Optional, and far more useful than prose. */
export const rejectPuzzle = (
  hash: string,
  reason: string,
  badLink: number | null,
): Promise<unknown> => post('/api/admin/reject', { hash, reason, badLink });

export const undoPuzzle = (hash: string): Promise<unknown> => post('/api/admin/undo', { hash });

// --------------------------------------------------------------------------
// 6b — refining a bank (planning.md 16.4)
// --------------------------------------------------------------------------

/** One decoy traded for another. Held in the UI until the puzzle is approved. */
export interface BankEdit {
  removed: string;
  added: string;
}

export interface SwapResponse {
  hash: string;
  bank: string[];
  decoys: string[];
  bankEdits: BankEdit[];
}

export interface SwapOption {
  word: string;
  /** How tempting the generator rates it. Lower is an easier bank. */
  temptingness: number;
  source: string;
}

/**
 * Prove a set of edits without saving them.
 *
 * The engine holds a veto: a swap that would give the puzzle a second valid
 * solution is refused with the reason, and the puzzle is left untouched. The
 * edits stay in component state until `approvePuzzle` carries them.
 */
export const previewSwap = (hash: string, edits: BankEdit[]): Promise<SwapResponse> =>
  post('/api/admin/swap', { hash, edits });

/**
 * Replacements the engine would actually accept.
 *
 * A POST because it takes edits the reviewer has not saved yet — a list of
 * pairs a query string has no natural encoding for. It writes nothing.
 */
export const fetchSwapOptions = (
  hash: string,
  removed: string,
  edits: BankEdit[],
): Promise<{ options: SwapOption[] }> =>
  post('/api/admin/swaps', { hash, removed, edits });

// --------------------------------------------------------------------------
// 6c — the pool, and choosing a date (planning.md 16.2, 16.6)
// --------------------------------------------------------------------------

export interface PoolPuzzle extends QueuePuzzle {
  bankEdits: BankEdit[];
  /** null while it is approved but undated — the state 16.2 exists to create. */
  date: string | null;
}

export interface Slot {
  date: string;
  hash: string | null;
}

export interface PoolResponse {
  scheduled: PoolPuzzle[];
  pooled: PoolPuzzle[];
  /** A contiguous run. `date == epoch + (id - 1)` days leaves no room for gaps. */
  slots: Slot[];
  archive: { count: number; lastDate: string | null; nextDate: string };
}

export const fetchPool = (): Promise<PoolResponse> => request('/api/admin/pool');

/**
 * Put an approved puzzle on a date.
 *
 * `warnings` is 16.6: the corpus checks that fail loudly at export, asked while
 * the reviewer can still pick a different day. They never block.
 */
export const schedulePuzzle = (
  hash: string,
  date: string,
): Promise<{ date: string; warnings: string[] }> =>
  post('/api/admin/schedule', { hash, date });

/** Back to the undated pool. Deliberately not the same act as unapproving. */
export const unschedulePuzzle = (hash: string): Promise<unknown> =>
  post('/api/admin/unschedule', { hash });
