"""Linkage offline puzzle-generation engine.

Three tiers (planning.md 4.1):

    cli.py          Presentation  -- Typer commands, human-facing output
    domain/         Domain        -- pure logic. No I/O, no network, no files.
    data/           Data Access   -- downloads, parsing, wordfreq, pickles

Dependencies point inward: `domain` imports nothing from `data` or `cli`.
"""

__version__ = "0.1.0"
