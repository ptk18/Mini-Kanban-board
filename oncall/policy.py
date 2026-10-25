"""Read one value from autonomy-policy.yaml without a YAML dependency.

    python3 oncall/policy.py responder.max_turns
    python3 oncall/policy.py actions.clear_demo_fault.automatic

The file is simple two/three-level YAML with `key: value` lines; this walks
indentation. Prints the scalar, or nothing when the path does not exist.
"""

import sys
from pathlib import Path


def lookup(path: str) -> str:
    wanted = path.split(".")
    stack: list[str] = []
    for raw in (Path(__file__).with_name("autonomy-policy.yaml")).read_text().splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip() or line.lstrip().startswith("-"):
            continue
        indent = (len(line) - len(line.lstrip())) // 2
        key, _, value = line.strip().partition(":")
        stack = stack[:indent] + [key]
        if stack == wanted:
            return value.strip().strip('"').strip("'")
    return ""


if __name__ == "__main__":
    print(lookup(sys.argv[1]))
