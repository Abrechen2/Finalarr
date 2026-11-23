# Releasing

Releases are cut by pushing a tag to GitHub; `.github/workflows/release.yml` runs CI on
the tagged commit, builds the image, starts it once (`/health`), pushes it to GHCR with an
SBOM and provenance, signs it with cosign (keyless) and creates the GitHub release from
the matching `CHANGELOG.md` section.

Python libraries are pinned with hashes in `backend/requirements.txt`, so a release
candidate and its final build ship the same versions. Dependabot updates it; to change it
by hand after editing `pyproject.toml`:

```sh
cd backend && uv pip compile pyproject.toml --generate-hashes --python-version 3.12 \
  --universal -o requirements.txt
```

## Release candidate

1. `backend/VERSION` holds the upcoming version (e.g. `0.4.0`); the CHANGELOG section
   `## [0.4.0]` describes it.
2. `git tag v0.4.0-rc.N && git push github v0.4.0-rc.N` (and to the Forgejo mirror).
3. Result: `ghcr.io/abrechen2/finalarr:0.4.0-rc.N` and `:rc-latest` (amd64), GitHub
   pre-release.

## Final version

1. Soak the last release candidate on a real library; take a backup first
   (`docker exec finalarr python -m finalarr.backup`).
2. CHANGELOG: replace "not released yet" with the date.
3. Tag the commit the tested release candidate was built from: `git tag v0.4.0 <commit>`.
   The workflow builds only arm64, starts it, and joins it with the candidate's tested
   amd64 image into `0.4.0`, `0.4` and `latest`; it refuses a commit without a candidate.
4. Unraid: in `unraid/my-finalarr.xml` drop ` Status:Beta` from `<Category>` for 1.0,
   copy the template to `Abrechen2/docker-templates` (Community Applications indexes that
   repository), then install and update once through CA.
5. Verify: `docker pull ghcr.io/abrechen2/finalarr:latest` on amd64 and (cosign v3 or newer)
   `cosign verify ghcr.io/abrechen2/finalarr:0.4.0 --certificate-identity-regexp
   'https://github.com/Abrechen2/Finalarr/' --certificate-oidc-issuer
   https://token.actions.githubusercontent.com`.
