# Contributing

Thanks for helping! Bugs and ideas go into
[issues](https://github.com/Abrechen2/Finalarr/issues), questions into
[discussions](https://github.com/Abrechen2/Finalarr/discussions).

## Pull requests

1. Fork, then branch off `main`: `feat/…`, `fix/…`, `docs/…`, `refactor/…`, `chore/…`.
2. Write the failing test first; a bug fix starts with a test that fails on the old code.
   New code needs 80 %+ coverage; the season evaluator (`finalarr.core`) keeps full branch
   coverage, and every evaluator bug becomes a YAML case in `backend/tests/core/cases/`.
3. Run the checks:
   - `backend/`: `ruff check . && ruff format --check . && mypy && pytest --cov`
   - `frontend/`: `npm run typecheck && npm run lint && npm run format:check && npm test`
   - optional: `e2e/run.sh` (end-to-end with a demo Sonarr)
4. Conventional Commits (`feat:`, `fix:`, …); the body says *why*.
5. Open the PR against `main`; CI must be green.

## Conventions

- Code, comments and docs in English. UI strings: German and English in the same change
  (`frontend/src/i18n/de.json`, `en.json`).
- Files stay under ~400 lines (800 at most); match the style of the file you touch.
- Never commit secrets; configuration comes from the environment.
- The visual identity is described in [docs/DESIGN.md](docs/DESIGN.md).
