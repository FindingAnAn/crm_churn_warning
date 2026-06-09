"""Monthly churn pipeline entrypoint.

Preferred implementation lives in ``pipelines.churn.cli``. This module keeps a
short monthly-oriented command available:

    python -m pipelines.monthly.monthly_cli
"""

from __future__ import annotations

import sys

from pipelines.churn.cli import main


if __name__ == "__main__":
    sys.exit(main())
