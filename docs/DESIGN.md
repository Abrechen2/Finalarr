# Finalarr design — "Crescendo"

Finalarr is about one moment: the season building up to its finale. The identity draws
from that arc — episodes rising toward the last one, the late hour when finales air, and
the gold of something finished. It is Finalarr's own look; it does not borrow from the
maintainer's other tools or from Sublarr. The only foreign mark is the small
"A project by `<abrechen2 />`" credit in the footer, About page and README.

## Mark

A tally of five: four upright strokes count the episodes, the fifth — a diagonal in
Finale gold — closes the bundle. Counted to the end. It reads at 16 px (four strokes, one
gold slash) and at 512 px. App icon: the mark on a Night square with a 22 % corner radius
(`assets/icon.svg`, `assets/icon-512.png`, `frontend/public/favicon.svg`). Wordmark:
"Finalarr" in Unbounded 700, "arr" in the muted colour. Never recolour single strokes,
never animate the mark in the UI chrome.

## Colour

Two accents with fixed meanings, everything else quiet:

| Token | Dark (default) | Light | Meaning |
|---|---|---|---|
| `--bg` Night / Lavender paper | `#191529` | `#F6F4FA` | page |
| `--surface` Dusk / White | `#231E35` | `#FFFFFF` | panels |
| `--line` | `#352E4D` | `#E2DCEC` | 1 px borders |
| `--ink` | `#EFEAF7` | `#1B1726` | text |
| `--muted` | `#A49CB8` | `#5F5873` | secondary text |
| `--accent` Dusk rose | `#E5608A` | `#C2335F` | in progress: airing, progress bars, primary buttons, focus |
| `--gold` Finale gold | `#F2C14E` | `#9A6E08` | finished: finale, complete season, the last bar of the mark |
| `--sky` | `#7FB2F0` | `#2F6DB5` | aired, files still missing (waiting on the library) |
| `--ok` | `#4CC38A` | `#187A4C` | delivered |
| `--bad` | `#F0605A` | `#B42318` | failed, count disputed |

Gold is reserved for "done". If something is gold, a season or finale is complete —
nothing else in the interface may use it, not even hover states.

## Type

- **Unbounded** (OFL) — wide, poster-like display face, the voice of anime and series
  title cards. Logotype and page titles only.
- **Atkinson Hyperlegible Next** (OFL) — body, controls and every number. Built for
  legibility, which matters for an open-source tool used by anyone. Counts like `7/12` and
  `S03E05` use its tabular figures instead of a monospace face.

Self-hosted through `@fontsource`; no font is loaded from a third party.

Scale (rem): 0.75 · 0.875 · 1 (body, 1.5 line height) · 1.25 · 1.75 (page title,
Unbounded 700, tight tracking). Sentence case everywhere; no all-caps labels.

## Shape and layout

- Radius 10 px on panels, 6 px on controls, full round on progress bars and the mark's
  bars — the round bar is the recurring motif.
- Borders over shadows; no gradients, no glow.
- Episode grid: filled rose = on disk, outlined ink = aired without file, dashed muted =
  upcoming, gold = the season finale. The grid is the most "Finalarr" element of the UI.
- A finished season's progress bar turns gold; that colour change is the one moment of
  emphasis — no other motion in the chrome.

## Review against defaults

- *Near-black with one bright accent* — avoided: the base is a clearly violet night
  (`#191529`, not a tinted black), and the two accents carry meaning (progress vs. done)
  instead of decoration.
- *Monospace for data labels* — dropped (the first build used JetBrains Mono for counts);
  numbers use tabular figures of the body face.
- *Ring/progress-circle logo* — the first concept (a 12-segment ring) read as a generic
  loader and came from the maintainer's own palette.
- *Rising bars* — the second concept (five bars rising to a gold one) read as a mobile
  signal indicator; replaced by the tally, which says "counted to the end" and is not
  mistaken for a common UI glyph.
