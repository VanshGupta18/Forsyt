# Forsyt Documentation

## New here? Start with this

**What is a GPR index?** GPR stands for "Geopolitical Risk." It's a single
number, published daily, that tries to answer "how much is the news talking
about scary geopolitical stuff right now?" — wars, terrorist attacks,
sanctions, nuclear threats, coups, and similar events. It's not a measure of
actual economic damage or a stock-market prediction; it just tracks *news
attention* to that kind of risk. By convention, the number is scaled so that
**100 = an average/baseline day**, and higher numbers mean more/scarier
coverage than usual. This project builds its own version of that index by
reading and scoring real news articles, closely following an academic
methodology (Caldara & Iacoviello 2022; Iacoviello & Tong 2026) so the result
can be checked against the original published index.

**What is GDELT/GKG?** [GDELT](https://www.gdeltproject.org/) is a free,
public project that scans huge numbers of news articles from around the
world every 15 minutes and publishes structured data about each one — what
themes it covers (e.g. "armed conflict," "sanctions"), what locations it
mentions, and how negative/emotional its tone is. GKG ("Global Knowledge
Graph") is the specific GDELT data feed this project downloads and scores.
It's the raw material: this module reads GKG files, decides which articles
are about geopolitical risk, and turns that into the daily index.

**Why is there a "warmup era" and a "product era"?** This project didn't
always have its own dedicated India news source. Early on, it ran on GDELT's
global feed (tens of thousands of articles/day) just to calibrate the
scoring logic — that's the "warmup era" and its numbers are for internal
testing only, never shown to real users. Once a dedicated India-news feed
was scraping enough articles/day, the project switched over to scoring that
instead — that's the "product era," and its numbers are what actually ship
to the app/API. Because those two eras have wildly different article volumes
(tens of thousands per day vs a few hundred), they have to be normalized
(scaled to average 100) **separately** — mixing them into one scale would
make the low-volume era's scores look artificially tiny. See
[GPR Theory §9](./gpr-theory.md#9-split-era-normalization-2026-product) for
the full explanation.

Once those three ideas make sense, the two documents below go deep on the
actual formulas:

| Document | Description |
|----------|-------------|
| [GPR Theory & Calculations](./gpr-theory.md) | Full theory, formulas, split-era normalization, incremental scoring, logs |
| [Corridor Risk Index](./corridor-theory.md) | Corridor matcher, threat × exposure, split-era, validation |

For setup, GDELT warmup, and quickstart commands, see the [project README](../README.md) and [GDELT warmup runbook](../../docs/GDELT_WARMUP.md).
