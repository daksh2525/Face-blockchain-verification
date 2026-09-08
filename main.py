"""
main.py

CLI entrypoint for the Face Identification & Blockchain Verification
pipeline.

Usage:
    python main.py --image input/A.jpg
"""

import argparse
import sys

from app.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Face Identification & Blockchain Verification pipeline"
    )
    parser.add_argument(
        "--image",
        required=True,
        help="Path to the input face image (e.g. input/A.jpg)",
    )
    args = parser.parse_args()

    verified = run_pipeline(args.image)
    sys.exit(0 if verified else 1)


if __name__ == "__main__":
    main()