# Linkage

A daily mini word puzzle about the hidden connective tissue between ideas.

    APPLE -> newton -> gravity -> moon -> tide -> OCEAN

Connect a start word to an end word with a ladder of exactly four intermediate
words, chosen from a bank salted with plausible red herrings. You get three
lives, and after each guess you learn only *how many* slots are correct --
never which ones.

See [planning.md](planning.md) for the full design and architecture.

## Status

| Phase | What | State |
|---|---|---|
| 1 | Data engine -- ConceptNet graph | **in progress** |
| 2 | Puzzle generator + human review | not started |
| 3 | Frontend scaffold (Vite/React/TS) | not started |
| 4 | Game loop and logic | not started |
| 5 | Polish and share | not started |

## Repository layout

    engine/     Python. Offline puzzle generation. Run locally, not in CI.
    web/        TypeScript. The static client. (Phase 3)
    data/       Raw datasets and the built graph. Gitignored, regenerable.
    planning.md The blueprint.

## Quick start (engine)

```bash
python -m pip install -e engine
python -m nltk.downloader wordnet omw-1.4
linkage build-graph
linkage inspect apple
```

`build-graph` downloads the ConceptNet assertions dump (~1.2 GB) on first run
and caches it under `data/raw/`. Budget 20-40 minutes for the full build.

Run `linkage --help` for the full command list.

## Attribution

This project uses **[ConceptNet 5.7](https://conceptnet.io)**, a freely
available semantic network built from many sources, created by Robyn Speer and
collaborators at the Commonsense Computing Initiative.

ConceptNet is licensed under
**[Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/)**.

Because the puzzle data in this repository is derived from ConceptNet, that
derived data is distributed under the same **CC BY-SA 4.0** licence. This
applies to:

- `web/public/puzzles/**`
- `engine/fixtures/verification-subgraph.json`

Word frequency data comes from
[`wordfreq`](https://github.com/rspeer/wordfreq) (Robyn Speer), and part-of-speech
information from [WordNet](https://wordnet.princeton.edu/) via
[NLTK](https://www.nltk.org/).

## Licence

Source code is [MIT](LICENSE). Derived puzzle data is CC BY-SA 4.0, as above.
