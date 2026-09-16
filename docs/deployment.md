# Linkage — Deployment

> The companion to §12 of [`../planning.md`](../planning.md). §12 keeps only
> what constrains the rest of the project; this document is the full audit
> and the plan. Same move `docs/engine.md`, `docs/design.md` and
> `docs/admin.md` already made — only whoever is doing the deploy needs this
> level of detail.
>
> **Status:** proposed · scaffolding checked in · not yet deployed.
> **Host: Netlify** *(revised 2026-09-13, superseding an earlier GitHub Pages
> plan — see §2 for why)*. Every finding below was measured against the repo,
> not assumed from the plan.

---

## 1. The audit — what §12 originally assumed vs. what exists

The first pass through this document was written against a GitHub Pages
plan that turned out to be entirely unbuilt. The platform choice has since
changed to Netlify, but the underlying audit — what's actually finished
versus what's only ever been described — still holds, because none of it
was host-specific:

| Claim in the original plan | Checked | Actual |
|---|---|---|
| "GitHub is already connected... no setup needed" | `git remote -v`, `gh api repos/.../pages` | Remote is set. Pages was never enabled (`has_pages: false`) — moot now, since the host changed, but confirms nothing was actually turned on before this document existed. |
| `.github/workflows/test.yml`, `deploy.yml` | `find .github/workflows` | Directory didn't exist. **`test.yml` now does** (added alongside this revision); there is deliberately no `deploy.yml` under the Netlify plan — see §3. |
| `web/public/puzzles/**` is committed, real output | `manifest.json`, `puzzles/README.md` | `manifest.json` says `"count": 1`. The one file present (`2026-10-01.json`) is, by its own committed README, *"a hand-encoded development fixture, not output of `linkage export`."* **Zero real puzzles have shipped through the actual pipeline.** |
| Human review gate producing an archive | `engine/decisions.json` | 900 candidates generated, **46 reviewed, 14 accepted, 0 scheduled**. The Schedule screen (docs/admin.md §12.2) has never been used on real content. |
| Engine tests pass on fixtures alone | `pytest` from `engine/` | **603 passed, 22 skipped**, no network. |
| Web tests pass | `npm run test` | **124 passed**, 8 files. |
| `npm run build` succeeds; admin excluded | `npm run build` | Succeeds. `assert-no-admin: clean (6 files checked)`. Bundle: **169.6 KB JS / 15.6 KB CSS**, gzip **54.8 KB / 4.2 KB** — matches the "~50 KB app" promise. Reconfirmed after the `base` path change below; identical result. |
| `base` path set correctly | `vite.config.ts`, `main.tsx` | Now `base: '/'` (was `/Linkage/'` under the Pages plan) — Netlify roots the site, so this is Vite's default rather than a value to get right. |
| LICENSE / attribution present | `LICENSE`, `README.md`, `puzzles/README.md` | Present, unaffected by the hosting change. |
| Favicon, OG/meta tags | `index.html` | Still neither exists — unaffected by the hosting change, still an outstanding Phase 5 item. |
| `EPOCH_DATE` | `engine/config.py` | `2026-09-16`. |

**What this means:** the game itself is deployment-ready as code, on any
static host. The deployment *machinery* and the *content* that would run
through it are the two real gaps, and they're independent of which
platform serves the files — switching to Netlify closes zero of them by
itself. §6 keeps them as separate tracks for exactly that reason.

---

## 2. Why Netlify, and what changed from the GitHub Pages plan

Three platforms were actually compared for the game: GitHub Pages (the
original pick, purely because the repo already lived there), Render, and
Netlify. The deciding factors:

- **GitHub Pages has no header control.** §5.3 below (manifest caching at
  the daily rollover) was, under the Pages plan, an *accepted residual
  risk* — there was no way to configure a shorter cache lifetime on
  `manifest.json` specifically. Netlify's build config can set response
  headers per path, which turns that from "accepted risk" into "actually
  fixed" (see the `[[headers]]` block in `netlify.toml`, §3).
- **Custom-domain migration is a wash between Netlify and Render.** Both
  make moving from a platform subdomain (`<site>.netlify.app` /
  `<site>.onrender.com`) to a bought domain equally simple: add the domain
  in the dashboard, point a CNAME (or delegate nameservers for the
  simplest path), get free automatic HTTPS via Let's Encrypt either way.
  This was the one open question worth actually comparing, and it came
  back a tie.
- **With the platform question a tie, "most of this project's other work
  already lives on Netlify" is a legitimate tiebreaker.** One dashboard,
  one set of habits, one less thing to context-switch on.

**What this changes mechanically, all reflected in the code already:**

- `web/vite.config.ts`: `base` is now `'/'` — a Netlify site is served at
  its domain root, never a project subpath, so there's no
  GitHub-Pages-style path to misconfigure. `HttpPuzzleRepository` still
  reads `import.meta.env.BASE_URL` rather than a hardcoded path (unchanged
  — see §4.3's note on why that abstraction was worth keeping even now
  that it resolves to a constant).
- `web/netlify.toml` (new, committed): build config, replacing the
  `deploy.yml` GitHub Actions workflow the original plan called for. See §3.
- `.github/workflows/test.yml` (new, committed): unchanged in purpose from
  the original plan — it never depended on which host serves the built
  output.

---

## 3. The deploy pipeline that now exists

### 3.1 `test.yml` — the PR gate (unaffected by the hosting change)

```yaml
name: test
on: pull_request

jobs:
  engine:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -e .
        working-directory: engine
      - run: pytest
        working-directory: engine

  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
        working-directory: web
      - run: npm run typecheck
        working-directory: web
      - run: npm run lint
        working-directory: web
      - run: npm run test
        working-directory: web
      - run: npm run build
        working-directory: web
```

This stays even though Netlify's own build also runs `npm run test` — it
covers `engine/`'s pytest suite, which Netlify's build never touches (its
`base = "web"` deliberately keeps it from seeing anything else), and it
surfaces failures directly in the PR before a Netlify deploy preview even
starts building. Both jobs run on committed fixtures only, confirmed in
§1 — no dataset, no network, matching CLAUDE.md's constraint that CI must
never touch the 1.2 GB ConceptNet dump.

### 3.2 `netlify.toml` — build and deploy, no separate workflow

```toml
[build]
  base = "web"
  publish = "dist"
  command = "npm run test && npm run build"

[build.environment]
  NODE_VERSION = "20"

[[headers]]
  for = "/puzzles/manifest.json"
  [headers.values]
    Cache-Control = "public, max-age=300, must-revalidate"
```

Netlify's git integration reads this and builds + publishes on every push
to `main`, once the repo is connected in the dashboard (§6 Tier 1 — a
one-time manual action, not a code change, same category as enabling
Pages would have been). `base = "web"` means Netlify's build never sees
`engine/` or `engine/fixtures/` — the plaintext-answer-key exclusion
(planning.md §7.10, §12) is structural here rather than something to
remember, which is a small but real improvement over the Pages plan, where
keeping the fixture out of `dist/` depended entirely on Vite's own `public/`
resolution.

**There is no `deploy.yml`.** Netlify's own build *is* the deploy step,
and it produces a deploy preview on every PR automatically — something the
GitHub Pages plan would have needed a second workflow to replicate. Adding
a GitHub Actions deploy step on top would be two systems racing to publish
the same output; deliberately not built.

### 3.3 What neither pipeline may ever do

Same boundary as before, restated because the platform changed but the
constraint didn't: **no workflow and no Netlify build step may run
`build-graph`, `generate`, `review`, `export`, or `admin`.** Those need the
1.2 GB ConceptNet dump or are local-only by design (docs/admin.md §1).
`engine/candidates.json` and `approved.json` stay gitignored specifically
because they're local working state, not build input, on any host.

---

## 4. How local scheduling reaches the deployed site

Unchanged in shape from the original plan — this was never a
hosting-specific design, and the earlier conversation about a hosted
admin backend (considered and set aside) didn't change it either. The
chain, concretely:

1. Reviewer runs `linkage admin` locally, works the queue (approve, reject
   with a reason, edit a word — docs/admin.md §§2–5, 11). Writes only to
   `engine/decisions.json`.
2. Reviewer uses the Schedule screen to assign dates from the "next 7 open
   days" strip (docs/admin.md §12.2). Still only `decisions.json`.
3. Reviewer runs `linkage export`. This reads `decisions.json` and
   **writes** `web/public/puzzles/<date>.json`, `manifest.json`, and
   regenerates `engine/fixtures/verification-subgraph.json`.
4. `pytest` confirms the golden test holds against the refreshed subgraph.
5. `git add … && git commit && git push` — `decisions.json` is always
   committed, as durable human judgement.
6. On merge to `main`, Netlify's git integration builds and publishes
   `web/dist` automatically (§3.2) — no separate release step.
7. Netlify's CDN serves the new files, typically within a couple of
   minutes.

**`git push` is still the entire deploy.** Nothing about switching hosts
reopened the question of a remote admin backend — that idea was
considered separately and set aside in favor of keeping generation and
review entirely local, per docs/admin.md §1's original reasoning. If that
decision changes later, it's an independent piece of work from anything
in this document.

---

## 5. Constraints of a static SPA deploy on Netlify

### 5.1 `localStorage` — unaffected by the platform

Same as under any static host: already handled correctly (try/catch
everywhere, degrade to in-memory, confirmed by `progressStore.test.ts`'s
11 passing tests). No cross-device sync, no key migration across
`schemaVersion` bumps — both accepted limitations per planning.md §14/§2.8,
not gaps introduced or fixed by the hosting choice.

### 5.2 Loading, buffering, and blank-page failure modes

- **The base-path risk is structurally smaller now, but still needs a real
  check.** A Netlify site roots at `/`, so there's no subpath
  misconfiguration mode the way a GitHub Pages project site had — `base:
  '/'` is Vite's own default. That said, a local build cannot fully prove
  behavior on the real host (asset resolution, redirects, headers), so the
  first real Netlify deploy still gets a manual check (§6 Tier 4), the
  same discipline the Pages plan called for, just with less expected to
  go wrong.
- **Network failure and no-loading-skeleton are unchanged** — already
  correct per §8.7 and docs/design.md §8, and neither depends on the host.
- **Still missing: favicon and Open Graph tags.** Unaffected by the
  platform switch — still the same launch-blocking gap named in the
  original audit, since §1.4 makes "shareable" a non-negotiable constraint
  and a bare link preview undercuts it regardless of which CDN serves the
  page.
- **Still missing: an error boundary around `<App>`.** Same reasoning as
  before — cheap insurance, not a hosting concern, not built here since
  it's a code change beyond this task's scope.

### 5.3 CDN cache staleness at the daily rollover — now actually fixed

This was the one genuine platform-driven improvement. Under GitHub Pages,
`manifest.json`'s mutability (its `count` grows with every export batch)
against an uncontrollable edge-cache lifetime was named as **accepted
residual risk** — there was no lever to pull. Netlify's `[[headers]]`
config in `netlify.toml` (§3.2) sets `Cache-Control: public, max-age=300,
must-revalidate` on `manifest.json` specifically, capping staleness at five
minutes regardless of what Netlify's CDN would otherwise choose.

Dated puzzle files still need no special rule and didn't under Pages
either — `2026-10-02.json` and `2026-10-01.json` are different URLs, so a
stale cached copy of a past day is simply irrelevant once local midnight
moves the client on to a new filename. This is further de-risked by the
existing workflow: puzzles are exported and committed as a monthly batch
well ahead of their scheduled date (planning.md §7.7.1), not deployed
same-day.

### 5.4 The content constraint — unaffected by the platform, still the real gate

Per §1, the archive is still effectively empty and the one shipped file is
a dev fixture. Turning Netlify's deploy on and having real content ready
are independent gates on any host — §6 keeps them as separate tiers so
enabling the platform is never mistaken for having launched.

---

## 6. Remediation ladder

**Tier 1 — Deploy scaffolding.** *(mechanical, ~30–60 minutes)*
`.github/workflows/test.yml` and `web/netlify.toml` are now committed
(§3). What's left is a one-time manual action: create a Netlify site,
connect it to this GitHub repo, set the production branch to `main` — no
further config needed since `netlify.toml` carries the build settings.
This alone doesn't launch anything; with one fixture puzzle in the
archive, a live deploy today shows everyone the "no puzzle yet" state —
but it converts every future push into a tested, auditable deploy.

**Tier 2 — Custom domain (optional, independent of the tiers below).**
Buy the domain, add it in Netlify's Domain Management, point a CNAME (or
delegate nameservers for Netlify DNS, the simpler of the two paths). Free
automatic HTTPS via Let's Encrypt either way. This can happen before or
after Tier 3/4 — it doesn't block or get blocked by content readiness, so
sequence it whenever convenient. Note that switching *from*
`<site>.netlify.app` *to* the bought domain later, if the domain isn't
ready yet, is exactly as easy — this was the comparison point that made
Netlify vs. Render a tie in §2, not a reason to delay.

**Tier 3 — Launch-blocking polish.** *(cheap, ~1 hour, unaffected by the
hosting change)*
Favicon and Open Graph/Twitter-card meta tags in `index.html` — the
outstanding Phase 5 item, with real product cost given §1.4's sharing
requirement. A one-line error boundary around `<App>`.

**Tier 4 — Build the real archive.** *(the actual bottleneck: reviewer-days, not engineering-hours)*
Unaffected by any hosting decision. Finish reviewing enough of the 854
remaining candidates to clear planning.md §7.7.1's own launch bar of
~30–40 approved (round 1's rate: 46 reviewed → 14 accepted, consistent
with the 36% documented in §7.7.3 — roughly 85–110 more reviewed
candidates needed at that rate). Use the Schedule screen for the first
time on real content, placing `LAUNCH_WEEK_SIZE = 7` hand-picked easy
puzzles up front. Run `linkage export` for real, confirm `pytest` passes
against the resulting `verification-subgraph.json`, commit.

**Tier 5 — First real deploy and manual verification.**
Push the real archive to `main`; Netlify builds and publishes
automatically. On the live URL, confirm by hand: no console errors or
missing assets, today's puzzle loads (or the graceful pre-epoch message
shows), the `manifest.json` response carries the short cache header from
`netlify.toml`, `/admin` is unreachable in production, and a pasted link
renders a real preview once Tier 3 ships.

**Tier 6 — Explicitly deferred, unchanged from planning.md §14.**
Cloudflare Workers global stats, PWA/offline, a hosted admin backend (set
aside in the prior discussion for this project) — none of these decisions
are affected by the platform switch.

---

## 7. Pre-launch checklist

- [x] `.github/workflows/test.yml` added
- [x] `web/netlify.toml` added
- [x] `vite.config.ts` `base` updated to `'/'`
- [ ] Netlify site created and connected to the GitHub repo, production branch = `main`
- [ ] Custom domain purchased and pointed (optional, independent of the rest)
- [ ] Favicon + OG/Twitter meta tags in `index.html`
- [ ] Error boundary around `<App>`
- [ ] ~30–40 candidates accepted in `decisions.json` (currently 14)
- [ ] First real `linkage export` run; `manifest.json` count reflects it
- [ ] `pytest` green against the real `verification-subgraph.json`
- [ ] First deploy to the live Netlify URL; manual check per Tier 5
- [ ] `EPOCH_DATE` (2026-09-16) confirmed still the intended launch date

---

## 8. Risk-register entries (supersedes the equivalent GitHub Pages entries)

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 24 | ~~**No CI existed to catch a broken `main`**~~ | Was certain | — | **Resolved** — `test.yml` now runs on every PR (§3.1). |
| 25 | **Netlify-specific build/behavior bug only manifests on the real host** | Low | Blank page or missing asset in production despite a clean local build | `base: '/'` removes the one known class of this bug from the Pages plan; Tier 5's manual post-deploy check is still the real test, since local dev cannot fully reproduce the live CDN |
| 26 | ~~**`manifest.json` served stale from an uncontrollable edge cache**~~ | Was accepted residual risk under Pages | — | **Fixed, not just accepted** — `netlify.toml`'s `[[headers]]` caps `manifest.json` at a 5-minute cache (§5.3) |
| 27 | **Netlify deploy enabled while the archive is still the one-puzzle fixture** | Low, easy to do by accident once Tier 1 ships | Real visitors see an unfinished product | Tier 4 (content) is tracked independently of Tier 1 (hosting) specifically so connecting the Netlify site is never mistaken for "launched" |

---

## 9. Decision log

| Decision | Chosen | Rejected | Rationale |
|---|---|---|---|
| Host | **Netlify** *(revised 2026-09-13, was GitHub Pages)* | GitHub Pages, Render | Header control closes the manifest-caching risk outright rather than accepting it; custom-domain migration is a tie against Render; most other work already lives on Netlify |
| Deploy mechanism | **Netlify's native git integration** via `netlify.toml` | A `deploy.yml` GitHub Actions workflow (the original Pages plan) | Netlify's own build already does this and adds free PR deploy previews; a parallel Actions deploy would be two systems racing to publish the same output |
| PR gate | **Kept as a separate `test.yml`** | Relying on Netlify's build alone to gate quality | Netlify's build only ever sees `web/`; `engine/`'s pytest suite needs its own CI regardless of host |
| Puzzle review/scheduling | **Stays local-only** (docs/admin.md §1, unchanged) | A deployed admin backend (considered separately) | Set aside independently of this hosting decision — see the prior conversation on generation still needing the 1.2 GB dataset locally regardless of where review happens |
