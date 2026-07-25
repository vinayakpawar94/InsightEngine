"""Importing a :class:`~insightengine.core.codebook.Codebook` from a
legacy IBM Dimensions-era ``.sav`` file, via ``pyreadstat``.

**Verification status, stated precisely because it matters:**

* Variable/value-label reading (→ :class:`SingleQuestion`/
  :class:`NumericQuestion`/:class:`TextQuestion`) is genuinely tested
  against real ``.sav`` files created and read back with ``pyreadstat``
  itself. This surfaced a real, confirmed issue:
  ``pyreadstat`` returns value-label keys as ``float`` (e.g. ``1.0``),
  not ``int`` — handled by :func:`_coerce_label_key`, the same class of
  fix Phase 6 needed for pandas' own float-upcast behavior, for a
  different underlying reason.
* **Multiple-response set (MRSET) handling is NOT verified against a
  real Dimensions-produced file — it cannot be, in this environment.**
  ``pyreadstat.write_sav`` has no parameter for writing MRSET
  definitions at all (confirmed by inspecting its signature), so no
  synthetic round-trip test can exercise this code path; it is
  implemented strictly against ``pyreadstat``'s own C-extension source
  (``_readstat_parser.pyx``), which confirms ``mr_sets`` is a real,
  populated dict attribute shaped
  ``{name: {"type": str, "is_dichotomy": bool, "counted_value": ...,
  "label": str, "variable_list": [...]}}``. Only the
  ``is_dichotomy=True`` ("multiple dichotomy") shape is implemented,
  since it matches the binary-indicator-column convention already
  confirmed as the real legacy Dimensions pattern (Phase 7's
  ``MultiResponseExpansionTransformer``). ``is_dichotomy=False``
  ("multiple category" sets) is explicitly rejected, not silently
  mishandled.
* **A real, unresolved integration gap, found while building this:**
  a real ``.sav``'s MRSET subvariable names are whatever the original
  file used (e.g. ``Q8A``, ``Q8B``) — there is no guarantee they follow
  the ``"{question_id}_{category_code}"`` naming convention Phase 7's
  ``MultiResponseExpansionTransformer`` looks for. This module can
  correctly build the *metadata* shape (the ``MultiQuestion`` and its
  categories), but wiring the *data* columns into Phase 7's cleaning
  step requires either a column-renaming step (not built here) or a
  Phase 7 enhancement to accept an explicit name mapping (not built
  either). Flagged here as an open question, not solved.
"""

from __future__ import annotations

from pathlib import Path

import pyreadstat
from pyreadstat.pyclasses import MRSet

from insightengine.core.codebook import (
    Category,
    Codebook,
    MultiQuestion,
    NumericQuestion,
    Question,
    SingleQuestion,
    TextQuestion,
)
from insightengine.core.exceptions import MetadataParseError


def _coerce_label_key(key: object) -> int:
    """Reconcile a pyreadstat value-label key against the ``int``
    category-code contract — confirmed empirically that pyreadstat
    returns these as ``float`` (e.g. ``1.0``), not ``int``.
    """
    if isinstance(key, bool):
        raise MetadataParseError(f"Unexpected boolean value-label key: {key!r}.")
    if isinstance(key, int):
        return key
    if isinstance(key, float) and key.is_integer():
        return int(key)
    raise MetadataParseError(f"Value-label key {key!r} is not a whole number.")


def _build_categorical_question(name: str, label: str, value_labels: dict[float | int, str]) -> SingleQuestion:
    categories = tuple(
        Category(code=_coerce_label_key(code), label=str(text))
        for code, text in sorted(value_labels.items(), key=lambda item: repr(item[0]))
    )
    return SingleQuestion(id=name, label=label or name, categories=categories)


def _build_mrset_question(
    mrset_name: str,
    mrset: MRSet,
    column_labels: dict[str, str],
) -> MultiQuestion:
    if not mrset.get("is_dichotomy", False):
        raise MetadataParseError(
            f"MRSET {mrset_name!r} is a 'multiple category' set (is_dichotomy=False), "
            f"which this importer does not support — only 'multiple dichotomy' sets are "
            f"implemented. See this module's docstring."
        )
    variable_list = mrset.get("variable_list") or []
    if not variable_list:
        raise MetadataParseError(f"MRSET {mrset_name!r} has no constituent variables.")

    # Dichotomy subvariables don't carry their own category codes the
    # way a real category set would — each subvariable IS one category,
    # so codes are assigned by position (1-based) over variable_list.
    categories = tuple(
        Category(code=index, label=column_labels.get(var_name, var_name))
        for index, var_name in enumerate(variable_list, start=1)
    )
    label = mrset.get("label") or mrset_name
    return MultiQuestion(id=mrset_name, label=label, categories=categories)


class SavMetadataParser:
    """Imports a :class:`Codebook` from a legacy ``.sav`` file's
    variable/value labels and MRSET definitions.

    See this module's docstring for exactly which parts are genuinely
    tested versus grounded in source evidence alone.
    """

    def parse(self, source: Path) -> Codebook:
        if not source.is_file():
            raise MetadataParseError(f".sav file not found: {source}")

        try:
            _, meta = pyreadstat.read_sav(str(source), metadataonly=True)
        except Exception as exc:  # pyreadstat raises its own broad exception types
            raise MetadataParseError(f"Could not read .sav metadata from {source}: {exc}") from exc

        column_labels = dict(meta.column_names_to_labels)
        mrset_member_variables: set[str] = set()
        for mrset in meta.mr_sets.values():
            mrset_member_variables.update(mrset.get("variable_list") or [])

        questions: list[Question] = []
        for name in meta.column_names:
            if name in mrset_member_variables:
                # Belongs to an MRSET - represented once, via the MRSET
                # itself below, not as its own standalone question.
                continue

            # pyreadstat sets an explicit None for unlabeled variables
            # rather than omitting the key - confirmed empirically, since
            # `.get(name, name)` alone silently returned None instead of
            # falling back to the variable name for the first version of
            # this code, caught by this module's own test suite.
            label = column_labels.get(name) or name
            value_labels = meta.variable_value_labels.get(name)
            if value_labels:
                questions.append(_build_categorical_question(name, label, value_labels))
            elif meta.readstat_variable_types.get(name) == "string":
                questions.append(TextQuestion(id=name, label=label))
            else:
                questions.append(NumericQuestion(id=name, label=label))

        for mrset_name, mrset in meta.mr_sets.items():
            questions.append(_build_mrset_question(mrset_name, mrset, column_labels))

        return Codebook(questions)
