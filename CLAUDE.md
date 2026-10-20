# mlb-today

Daily MLB digest email. See `CONTEXT.md` for the glossary, `docs/adr/` for decisions, and
`.claude/docs/specs/mlb-today-v2-self-hosted-refactor-project-spec.md` for the v2 project spec.

## Linear

- linear_initiative: mlb-today (I-11)
- linear_team: NEU
- linear_repo: mlb-today

## Branch flow

- Work branches are cut from `main` and PRs target `main`.
- Every push to `main` publishes `ghcr.io/tomboone/mlb-today:latest`, which Watchtower deploys to the Mini.

## Toolchain (v2)

uv, ruff, pyright, pytest. Python 3.13. `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` before opening a PR.
