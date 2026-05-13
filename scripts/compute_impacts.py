"""Compatibility entrypoint for the WPTRA dashboard data pipeline."""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.pipeline import generate_all_data


def main() -> None:
    generate_all_data(fresh=True)


if __name__ == "__main__":
    main()
