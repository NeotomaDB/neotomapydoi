"""Ship minting log files to S3.

Called by `entrypoint.sh` after a scheduled run. The bucket is read from the
`DOI_LOG_BUCKET` environment variable, which the ECS task definition supplies.
If that variable is unset the script is a no-op, so the container can still be
run locally without AWS credentials.

Usage:
    python scripts/ship_logs.py <log_dir> <run_id>
"""

import os
import sys
from pathlib import Path


def ship_logs(log_dir: str, run_id: str) -> int:
    """Upload every log file in `log_dir` to `s3://$DOI_LOG_BUCKET/<run_id>/`.

    Args:
        log_dir (str): Directory holding the `*.log` files written by `ndbdoi.py`.
        run_id (str): Key prefix identifying this run, e.g. `2026-08-21T14-00-00Z`.

    Returns:
        int: 0 on success (including the no-op case), 1 if any upload failed.
    """
    bucket = os.getenv("DOI_LOG_BUCKET")
    if not bucket:
        print("DOI_LOG_BUCKET not set; skipping log upload.")
        return 0

    logs = sorted(Path(log_dir).glob("*.log"))
    if not logs:
        print(f"No log files found in {log_dir}; nothing to upload.")
        return 0

    import boto3

    client = boto3.client("s3")
    failures = 0
    for log in logs:
        key = f"{run_id}/{log.name}"
        try:
            client.upload_file(str(log), bucket, key)
            print(f"Uploaded s3://{bucket}/{key} ({log.stat().st_size} bytes)")
        except Exception as e:
            failures += 1
            print(f"Failed to upload {log.name}: {e}")

    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(ship_logs(sys.argv[1], sys.argv[2]))
