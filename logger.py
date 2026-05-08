import json
import os
import time


class JSONLLogger:
    """Writes one JSON object per line to logs/run_<timestamp>.jsonl.

    Each call to log() flushes immediately so the file is tail-able while
    the agent runs.
    """

    def __init__(self, run_id=None, log_dir="logs"):
        run_id = run_id or time.strftime("%Y%m%d_%H%M%S")
        os.makedirs(log_dir, exist_ok=True)
        self.path = os.path.join(log_dir, f"run_{run_id}.jsonl")
        self.fh = open(self.path, "w", buffering=1)  # line-buffered

    def log(self, **kwargs):
        kwargs.setdefault("ts", time.time())
        self.fh.write(json.dumps(kwargs, default=str) + "\n")

    def close(self):
        if not self.fh.closed:
            self.fh.close()
