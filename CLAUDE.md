# mlb-today

Daily MLB digest email. See `CONTEXT.md` for the glossary, `docs/adr/` for decisions, and
`.claude/docs/specs/mlb-today-v2-self-hosted-refactor-project-spec.md` for the v2 project spec.

## Linear

- linear_initiative: mlb-today (I-11)
- linear_team: NEU
- linear_repo: mlb-today

## Branch flow (v2 refactor, Linear project P-NEU-99)

- Work branches are cut from `release/v2` and PRs target `release/v2`, not `main`.
- `main` still deploys the Azure Functions app until the final cutover PR (NEU-1762) merges `release/v2` into it.

## Toolchain (v2)

uv, ruff, pyright, pytest. Python 3.13. `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` before opening a PR.
