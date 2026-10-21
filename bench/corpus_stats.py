"""Rebuild both corpora from the raw files and print their statistics."""
import json
import sys

from common import save  # noqa: F401  (sets sys.path)
from crshe import corpus

out = {}
for name, loader in (("telemetry", corpus.load_telemetry), ("beijing", corpus.load_beijing)):
    try:
        c = loader()
    except (FileNotFoundError, OSError) as exc:
        print(f"{name}: skipped ({exc})", file=sys.stderr)
        continue
    out[name] = c.summary()
    print(json.dumps(out[name]))
if out:
    save("corpus_stats.json", out)
