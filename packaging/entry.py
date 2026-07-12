"""PyInstaller entry script: a plain script avoids frozen-package __main__ quirks."""

import sys

from radix.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
