"""Eval support for T1 — ground-truth fixtures and the run cache.

Nothing here is pipeline logic. It exists so T1 can score `identify/` against labelled
images without a human labelling anything: the pokemontcg.io API record IS the label
(docs/GATES.md), so the download and the answer key are the same fetch.
"""
