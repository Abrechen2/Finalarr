# Contributing

- Branches: `feat/`, `fix/`, `chore/`, `docs/`, `refactor/` off `main`; Conventional Commits, the body explains *why*.
- TDD: write the failing test first; 80 %+ coverage on new code, the evaluator (`finalarr.core`) aims for full branch coverage. A bug fix starts with a test that fails on the old code.
- Backend: `ruff check . && ruff format --check . && mypy && pytest --cov` in `backend/`.
- Frontend: `npm run typecheck && npm run lint && npm run format:check && npm test` in `frontend/`.
- UI strings: German first, English mirror, in the same change.
- Files stay under ~400 lines (800 hard).
- Never commit secrets; configuration comes from the environment.
