# 0009 — The migration consolidates the historic module series

**Status:** Accepted
**Extends:** [ADR 0006](0006-sqlite-storage-instead-of-influxdb.md)
**Context:** The SolarEdge monitoring API changed what it reports as an optimizer's `identifier`, and the naming of an optimizer changed with it (`LogicalInfo.DISPLAY_ORDER_PREFIXES`). An InfluxDB history therefore holds the same physical module under several tag sets — a development installation carries three: the numeric optimizer id with today's name, the serial number prefix with the old `Optimizer …` name for a single day, and today's shape. Importing that history one to one copies the split into the local storage, where it becomes permanent.

## Decision: merge onto the series carrying the newest point

**Decision:** After an import, `influx_import.consolidate_modules` folds every `modules` series onto the one that holds the newest point for the same `serialnumber` and field, and drops the merged series. Where both hold a value for the same timestamp the target keeps its own. The step runs unconditionally and is idempotent — on an already consolidated database it finds nothing to merge.

**Context:** The serial number is the only tag that stayed stable across all shapes, so it is the key. Two alternatives were rejected. Deriving `identifier` from the serial number reproduces the current shape for this installation, but it assumes the monitoring API keeps returning the serial prefix for every installation — the migration would then invent an identifier rather than preserve one. Leaving the history untouched is defensible because no query reads `modules` back, but it hands every dashboard the job of stitching the shapes together, forever, and the migration is the one moment the history is rewritten anyway.

**Consequence:** The pre-change `identifier` is not preserved — a dashboard that pinned the numeric optimizer id has to be repointed at the serial number. The value written by the older shape loses a collision, which is what is wanted here: the shape written by the newer release was the complete snapshot of that hour. Merging happens per series pair rather than in one transaction, following the write style the retention job already uses; an interrupted run leaves a partially consolidated database that the next run finishes.
