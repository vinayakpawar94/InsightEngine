"""The Metadata Engine: parsing external questionnaire definitions into
a :class:`~insightengine.core.codebook.Codebook`.

Only the native YAML format is implemented in this phase
(:mod:`insightengine.metadata.parsers.yaml_native`). Legacy ``.sav``
import and other formats (Excel codebooks, Triple-S/DDI) are deferred to
later phases — see the implementation roadmap.
"""

from __future__ import annotations
