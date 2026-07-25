"""The legacy migration bridge: importing metadata from IBM Dimensions-era
``.sav`` files, and comparing new validation results against parsed
legacy QA output (a "shadow run").

**Read this before trusting anything in this package.** Every module
here states plainly which parts are verified against real, executable
tests and which parts rest on documentation/source evidence alone
because no real Dimensions-produced ``.sav`` file has ever been
available to test against — a limitation flagged at the very start of
this project's roadmap and never resolved. See each module's own
docstring for specifics; this package does not paper over that gap.
"""

from __future__ import annotations
