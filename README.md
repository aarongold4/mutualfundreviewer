# Mutual Fund Reviewer

Static affiliate/editorial site reviewing index funds, mutual funds, and robo-advisors
for long-term US investors. Bogleheads-adjacent tone: low costs win, hype loses.

Pure static HTML/CSS/JS output — drop `dist/` on any host (built for Hostinger).

## Build

```bash
pip install -r requirements.txt
python build.py
```

Output lands in `dist/` (cleared and rebuilt each run): ~145 pages, `sitemap.xml`,
`robots.txt`, and a copy of `static/`. Upload the **contents of `dist/`** to your web root.

## Project layout

```
data/
  site.json          # site config, tokens, author bio, nav, robo-advisor reviews
  funds/*.json        # 100 funds, split by family — the single source of truth
  compares.json       # 30 head-to-head comparison definitions
templates/            # Jinja2 templates
static/css|js/        # design system + calculator
build.py              # generator
dist/                 # build output (git-ignore this)
```

## Pages produced

- `/` homepage
- `/best-index-funds/` — the money page, ranked by expense ratio
- `/funds/{ticker}/` — 100 programmatic fund reviews
- `/compare/{a-vs-b}/` — 30 head-to-head comparisons
- `/expense-ratio-calculator/` — interactive vanilla-JS fee calculator
- `/index-vs-active/`, `/target-date-funds/`, `/robo-advisors/`
- `/funds/`, `/compare/` directories
- Legal: `/methodology/ /how-we-make-money/ /about/ /contact/ /privacy/ /terms/ /disclaimer/`

## Tokens to replace before launch

These ship as literal placeholders in the HTML so you can swap them post-build
(find-and-replace across `dist/`, or edit `data/site.json` and rebuild):

| Token | Where | What |
|---|---|---|
| `{{GA4_ID}}` | every page `<head>` | Google Analytics 4 measurement ID |
| `{{GSC_TOKEN}}` | every page `<head>` | Google Search Console verification |
| `{{BING_TOKEN}}` | every page `<head>` | Bing Webmaster verification |
| `{{FORM_ACTION}}` | `/contact/` | contact-form POST endpoint (e.g. Formspree) |
| `{{AFF_BETTERMENT}}` | `/robo-advisors/` | Betterment affiliate URL |
| `{{AFF_WEALTHFRONT}}` | `/robo-advisors/` | Wealthfront affiliate URL |
| `{{AFF_M1}}` | `/robo-advisors/` | M1 Finance affiliate URL |
| `{{AFF_IBKR}}` | `/robo-advisors/` | Interactive Brokers affiliate URL |
| `{{AFF_SOFI_INVEST}}` | `/robo-advisors/` | SoFi Invest affiliate URL |

All affiliate links already carry `rel="sponsored nofollow"`.

## ⚠️ Verify fund data before launch

Expense ratios and minimums live in `data/funds/*.json` with a single
`last_verified` date in `data/site.json`. **Index-fund figures were spot-checked;
several actively-managed funds' expense ratios are approximate and should be
re-confirmed against current prospectuses before you publish**, since active-fund
fees and share-class minimums drift. Update the JSON and the `last_verified` date,
then rebuild — every page's verified stamp, FAQ, schema, and tables update automatically.

## YMYL / compliance notes

- Author is presented as a writer/editor, **not** a licensed advisor (see `/about/`, `/disclaimer/`).
- No return projections anywhere except the calculator's neutral, user-driven compound-interest math.
- Affiliate disclosure on every page header + dedicated `/how-we-make-money/`.
- Every fund figure carries a last-verified date and "confirm against prospectus" language.

## Editing content

- **Add a fund:** add an object to the right `data/funds/*.json` (ticker, name, family,
  category, type, strategy, expense_ratio, minimum, inception, best_for, editorial[], alternatives[]).
  It auto-appears in the directory, family lists, and (if `index`/`target-date`) the best-funds rankings.
- **Add a comparison:** add `{a, b, intro, verdict}` to `data/compares.json` — both tickers must exist.
- **Edit a robo review:** edit the `robos` array in `data/site.json`.
