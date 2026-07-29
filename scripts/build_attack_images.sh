#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CATALOG="$PROJECT_ROOT/attacks/attack_catalog.yaml"

if [ ! -f "$CATALOG" ]; then
  echo "Attack catalog not found: $CATALOG" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to parse attack_catalog.yaml" >&2
  exit 1
fi

python3 - <<'PY' "$PROJECT_ROOT" "$CATALOG"
import sys
from pathlib import Path
try:
    import yaml
except Exception as exc:
    raise SystemExit(f"PyYAML is required: {exc}")
root = Path(sys.argv[1])
catalog = yaml.safe_load(Path(sys.argv[2]).read_text()) or {}
for attack_type, spec in catalog.items():
    image = spec.get('image')
    path = root / 'attacks' / attack_type
    if not image or not path.exists():
        raise SystemExit(f"invalid attack catalog entry: {attack_type}")
    print(f"{image}\t{path.relative_to(root)}")
PY

while IFS=$'\t' read -r image context; do
  echo "--- Building $image from $context"
  docker build -t "$image" "$PROJECT_ROOT/$context"
done < <(python3 - <<'PY' "$PROJECT_ROOT" "$CATALOG"
import sys
from pathlib import Path
import yaml
root = Path(sys.argv[1])
catalog = yaml.safe_load(Path(sys.argv[2]).read_text()) or {}
for attack_type, spec in catalog.items():
    print(f"{spec['image']}\tattacks/{attack_type}")
PY
)

echo "Attack image build completed."
