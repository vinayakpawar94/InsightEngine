"""The Data Engine: backend-agnostic tabular data access.

Nothing in this package knows about :class:`~insightengine.core.codebook.Codebook`
or questionnaire concepts. It exists solely to load rows from a file into
a queryable in-memory handle, and to let that handle's underlying engine
(pandas today; DuckDB/Parquet in a later phase) be swapped without
touching anything that consumes it — see :mod:`insightengine.data.base`.
"""

from __future__ import annotations
