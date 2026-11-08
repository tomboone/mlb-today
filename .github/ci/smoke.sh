#!/usr/bin/env bash
# Smoke test for the image. image-check passes the image tag as $1.
set -euo pipefail
image=$1

# mjml-python ships a compiled extension; prove its wheel loads on the slim base.
docker run --rm "$image" python -c "import mjml"

help=$(docker run --rm "$image" mlb-today --help)
echo "$help"
for command in run send preview health; do
  if ! grep -qw "$command" <<<"$help"; then
    echo "::error title=smoke::mlb-today --help doesn't list '$command'"
    exit 1
  fi
done

echo "smoke ok"
