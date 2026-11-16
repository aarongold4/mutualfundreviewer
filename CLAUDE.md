# Working on mutualfundreviewer.com

Aaron's cost-first index- and mutual-fund review + directory site. Static Python/Jinja2 → `dist/`.
Pen name **Nathan Blake** (writer/editor, not a licensed advisor). This file is the authoritative spec for
every session, scheduled or not. Read it first and follow it.

## Standing rule from Aaron (applies to every run)
This is Aaron's firm standing rule for all his finance sites, and nothing is out of scope:
1. **Check everything systematically** — every fund, every number, every claim, on every page, against the
   fund issuer's own filings.
2. **Correct everything systematically** — fix confirmed facts and the prose that depends on them; re-score and
   let rankings/order follow; mark merged/closed funds; apply renames without changing slugs; rewrite a review's
   prose only where its core story no longer holds.
3. **Report** — every change (old → new, with source URL), a specific "spot-check these" list, could-not-verify,
   needs-your-decision, and quality checks. Save to the Google Drive folder "mutualfundreviewer.com audits",
   SendUserFile it, and **email it to Aaron** (he wants these emailed, not only pushed).
4. **Suggest new content** — 3–5 ideas in `data/content_ideas.json` plus one draft guide as a `_drafts/` entry /
   draft PR. Aaron publishes from his Site Approvals page in Claude with a one-click Publish/Discard.

## Accuracy is paramount (Aaron's #1 rule)
- **Never invent a number or fact. Never publish anything you could not verify.** Anything you cannot confirm
  stays exactly as-is and is listed under "could not verify."
- **Filing-only corrections.** A figure is only changed when the fund **issuer's own filing** supports it:
  the summary prospectus, statutory prospectus, 497/497K, N-1A, N-CSR, or the issuer's official fund page / fact
  sheet. Third-party aggregators (Morningstar, Yahoo, etc.) are **corroboration only** — never the basis for a
  change on their own.
- **Convention lock.** The expense ratio is always the **net "Total Annual Fund Operating Expenses"** (after any
  fee waiver) as stated in the prospectus fee table, expressed as a percent (e.g. `0.04` = 0.04%). Do not mix in
  gross ER, acquired-fund fees shown separately, or an aggregator's differently-defined number.
- **Circuit breaker.** If a single run would change **more than 15** fund fields, STOP, commit nothing, and
  report it for Aaron to review — a jump that large almost always means a bad source or a parsing error, not 15
  real prospectus changes.

## Data layer (`data/`)
- `funds/*.json` — six issuer files (american, fidelity, schwab, trowe, vanguard, other), **100 funds total**,
  each a list of fund objects. Fields: `ticker, name, family, category, type (index|active), strategy,
  expense_ratio (% net), minimum ($), inception, best_for, editorial[], alternatives[]`.
- `site.json` — `last_verified` (YYYY-MM-DD) drives the public "Fund data last verified" stamp via build.py
  (`LAST_VERIFIED = SITE.get("last_verified", TODAY)`). Also nav/footer.
- `compares.json` — 30 head-to-head comparisons (`a`/`b` are tickers that must exist in the fund set).
- `content_ideas.json` — the editorial idea queue.
- `build.py` runs `validate_data()` first: ER must be in [0,3]%, minimum a non-negative int ≤ 1e8, required
  fields present, compare sides reference real tickers. It **refuses to build** on a violation — good; fix the
  data, don't weaken the gate.

## Advancing the verified date — do this EVERY run
On every run, after verifying whatever slice you verified this run, **set `data/site.json`'s `last_verified` to
today and commit**, even when you found **zero** corrections. A clean re-verification is a real result and must
move the public stamp; a quiet stretch with no change simply means nothing in the filings moved. Only skip the
date bump if the run was blocked before any verification happened (say so in the report). Never set the date for
funds you did **not** actually re-check this run — if you verify a rotating slice, say in the report which funds
were covered and that the rest carry their prior verification.

## Build + deploy
- Build: `python3 build.py` (installs from `requirements.txt` if needed: `pip install --break-system-packages -r requirements.txt`).
- Confirm the build succeeds, produces the expected pages, `dist/index.html` exists, and **no `{{PLACEHOLDER}}`
  (uppercase `{{TOKEN}}`) remains anywhere in `dist/`**. Normal Jinja in templates is fine. **Never edit `dist/`.**
- Deploy = **push to `main`**. The GitHub Action (`.github/workflows/deploy.yml`) builds and publishes `dist/`
  to the `deploy` branch; Hostinger serves the `deploy` branch and updates within a couple of minutes.
- Commit author identity: set `git config user.name "Aaron Gold"` and reuse the repo's existing commit email with
  `git config user.email "$(git log -1 --format='%ae')"` — do **not** hardcode Aaron's email in any prompt or script.
- Commit messages end with the standard Claude attribution lines.

## Approvals (never send Aaron to GitHub)
Aaron approves draft guides on his **Site Approvals page in Claude**, not on GitHub. When a run proposes a draft,
add an `ArtifactData` row (collection "drafts", doc_id `mutualfundreviewer-<idea id>`; fields site
"mutualfundreviewer.com", idea_id, title, why_now, doc_url, pr_url, trigger_id, created, updated, status
"pending", result_url null, result_note null) and send a PushNotification
"New mutualfundreviewer.com draft ready: <title>. Open Site Approvals in Claude to publish or discard."
Never tell Aaron to merge a PR, open GitHub, or press Run now.

## Privacy / identity
Pen name is **Nathan Blake**. Never put Aaron's personal name, personal email, or any contact info on the site or
in any committed file without his explicit permission.
