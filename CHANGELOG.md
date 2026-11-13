# Changelog

All notable changes to Finalarr are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow SemVer.

## [Unreleased]

### Added
- Finalarr refuses to start without `FINALARR_API_KEY` (20+ characters) and a valid `FINALARR_SECRET_KEY`, and says which one is missing.
- API access with the `X-Api-Key` header or a login cookie; login is limited to 5 attempts per minute, and rotating the key ends all sessions.
- Project skeleton: Flask backend with `/health`, React frontend, Docker image (non-root, PUID/PGID), Compose files and Forgejo CI.
