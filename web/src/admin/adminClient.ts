/**
 * Transport for the local review tool (docs/admin.md 3).
 *
 * No auth header, because there is no auth: the server binds 127.0.0.1 and the
 * safest gate is nothing exposed (docs/admin.md 1). Vite proxies `/api/admin`
 * to it, so this is same-origin and CORS never enters the picture.
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
  bankEdits: WordEdit[];
  manualEdges: ManualEdge[];
  /** null unless scheduled — the state docs/admin.md 2 exists to create. */
  date: string | null;
}

export interface QueueCounts {
  total: number;
  pending: number;
  decided: number;
  approved: number;
  scheduled: number;
  rejected: number;
  returned: number;
}

export interface QueueResponse {
  puzzles: QueuePuzzle[];
  /** Approved, then pulled back for another look. Its own lane (12.1). */
  returned: QueuePuzzle[];
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

/** `edits` and `manualEdges` ride along; the server re-proves both before storing. */
export const approvePuzzle = (
  hash: string,
  edits: WordEdit[] = [],
  manualEdges: ManualEdge[] = [],
): Promise<unknown> =>
  post('/api/admin/approve', { hash, edits, manualEdges });

/** `badLink` indexes `chain` links, 0..4. Optional, and far more useful than prose. */
export const rejectPuzzle = (
  hash: string,
  reason: string,
  badLink: number | null,
): Promise<unknown> => post('/api/admin/reject', { hash, reason, badLink });

export const undoPuzzle = (hash: string): Promise<unknown> => post('/api/admin/undo', { hash });

/**
 * Approved → back to the review queue, into its own lane (docs/admin.md 12.1).
 *
 * Not the same as `undoPuzzle`, which deletes the verdict and drops the puzzle
 * back among the 867 pending — where the reviewer would never find it again.
 * Records no note: the only feedback that reaches the system is approve and
 * reject.
 */
export const sendBackPuzzle = (hash: string): Promise<unknown> =>
  post('/api/admin/revisit', { hash });

// --------------------------------------------------------------------------
// Editing by hand (docs/admin.md 11)
// --------------------------------------------------------------------------

/** Which part of the puzzle an edit touches. `index` positions a solution edit. */
export interface WordEdit {
  field: 'start' | 'end' | 'solution' | 'bank';
  removed: string;
  added: string;
  index?: number;
}

/** A link the reviewer asserted that ConceptNet does not carry. */
export type ManualEdge = [string, string, number];

export interface EditResponse {
  hash: string;
  start: string;
  end: string;
  solution: string[];
  chain: string[];
  bank: string[];
  decoys: string[];
  /** Blocking. Uniqueness and the chords that manufacture it — nothing else. */
  refusals: string[];
  /** Never blocking. What the tool noticed; the reviewer overrules it freely. */
  notes: string[];
  /** Rungs now resting on the reviewer's word rather than ConceptNet's. */
  assertedLinks: number[];
  /** Rungs with no link from either source — each offers to be asserted. */
  brokenLinks: number[];
  ok: boolean;
  bankEdits: WordEdit[];
  manualEdges: ManualEdge[];
}

/**
 * Prove an edit without saving it.
 *
 * The reviewer's judgement governs whether a chain reads (docs/admin.md 11), so
 * a rung ConceptNet lacks comes back as a *note* once asserted, not a refusal.
 * The machine keeps one veto: a second valid arrangement, which is arithmetic
 * over 7,920 orderings rather than a matter of taste.
 */
export const previewEdit = (
  hash: string,
  edits: WordEdit[],
  manualEdges: ManualEdge[] = [],
): Promise<EditResponse> => post('/api/admin/edit', { hash, edits, manualEdges });

export interface SwapOption {
  word: string;
  /** How tempting the generator rates it. Lower is an easier bank. */
  temptingness: number;
  source: string;
}

/**
 * Replacements the engine would actually accept.
 *
 * A POST because it takes edits the reviewer has not saved yet — a list of
 * pairs a query string has no natural encoding for. It writes nothing.
 */
export const fetchSwapOptions = (
  hash: string,
  removed: string,
  edits: WordEdit[],
  manualEdges: ManualEdge[] = [],
): Promise<{ options: SwapOption[] }> =>
  post('/api/admin/swaps', { hash, removed, edits, manualEdges });

// --------------------------------------------------------------------------
// The pool, and choosing a date (docs/admin.md 7, 8, 12.2)
// --------------------------------------------------------------------------

export interface Slot {
  date: string;
  hash: string | null;
}

export interface PoolResponse {
  scheduled: QueuePuzzle[];
  pooled: QueuePuzzle[];
  /** The whole run. `date == epoch + (id - 1)` days leaves no room for gaps. */
  slots: Slot[];
  /** The next seven free ones — a week is the unit a person plans in (12.2). */
  openDays: string[];
  archive: { count: number; lastDate: string | null; nextDate: string };
}

export const fetchPool = (): Promise<PoolResponse> => request('/api/admin/pool');

/**
 * Put an approved puzzle on a date.
 *
 * `warnings` is docs/admin.md 7: the corpus checks that fail loudly at export,
 * asked while the reviewer can still pick a different day. They never block.
 */
export const schedulePuzzle = (
  hash: string,
  date: string,
): Promise<{ date: string; warnings: string[] }> =>
  post('/api/admin/schedule', { hash, date });

/** Back to the undated pool. Deliberately not the same act as unapproving. */
export const unschedulePuzzle = (hash: string): Promise<unknown> =>
  post('/api/admin/unschedule', { hash });
