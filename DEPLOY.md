# Deploy — mutualfundreviewer.com

Same pattern as onlinebankreview.com: push to `main` → GitHub Action rebuilds →
publishes the built site to the `deploy` branch → Hostinger auto-deploys `deploy`.

## One-time setup

1. **Repo** — `aarongold4/mutualfundreviewer` (already created and pushed by Claude).

2. **Secret for real tokens** — in GitHub: Settings → Secrets and variables → Actions →
   New repository secret named **`CONFIG_LOCAL`**. Paste the full JSON from your filled-in
   `config.local.json` (GA4, GSC, Bing, contact form, and the five affiliate URLs). The
   Action writes it to `config.local.json` at build time; it is never committed.
   Until this secret exists, the site builds fine but with analytics omitted and affiliate
   links pointing at each provider's public homepage.

3. **Hostinger** — in hPanel → Website → Git: connect the `aarongold4/mutualfundreviewer`
   repo and set the deployed branch to **`deploy`** (not `main`), deploying to `public_html`.
   The `deploy` branch contains the fully built static site at its root.

## Everyday flow

- Edit data/templates on `main`, push → the Action builds and updates `deploy` → Hostinger
  publishes within a minute or two.
- The Action fails (and does **not** deploy) if `build.py`'s guard trips: a leftover
  `{{UPPERCASE}}` token or fewer than 140 pages.

## Token values (fill into config.local.json / the CONFIG_LOCAL secret)

| Key | What |
|---|---|
| `analytics.ga4` | GA4 measurement ID (`G-XXXX…`) |
| `analytics.gsc` | Google Search Console verification token |
| `analytics.bing` | Bing Webmaster verification token |
| `contact.form_action` | Contact-form POST endpoint (e.g. Formspree) |
| `affiliate.betterment/wealthfront/m1/ibkr/sofi` | Affiliate URLs (each link already carries `rel="sponsored nofollow"`) |

See `config.local.example.json` for the exact shape.
