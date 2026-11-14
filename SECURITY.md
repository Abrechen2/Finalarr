# Security policy

Please report vulnerabilities **privately** through GitHub:
[Report a vulnerability](https://github.com/Abrechen2/Finalarr/security/advisories/new).
Do not open a public issue. You get a first answer within a week.

Only the latest release (and the current release candidate) gets fixes.

## Scope notes

- Finalarr is meant for your home network. The API key is the only credential; anyone
  holding it can set the Sonarr URL and channel URLs, which Finalarr then requests.
- `FINALARR_AUTH=local` skips the login for private addresses. Behind a reverse proxy set
  `FINALARR_TRUSTED_PROXIES`; otherwise forwarded requests always need the key.
- Stored Sonarr keys and channel URLs are encrypted with `FINALARR_SECRET_KEY`; logs strip
  keys, tokens and credential URLs.
