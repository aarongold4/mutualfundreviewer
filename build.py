#!/usr/bin/env python3
"""
build.py — Mutual Fund Reviewer static site generator.

Reads JSON from /data, renders Jinja2 templates from /templates, copies /static,
and writes a complete static site to /dist (plus sitemap.xml and robots.txt).

Usage:  python build.py
"""

import os, json, shutil, datetime, glob, re
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
DIST = os.path.join(ROOT, "dist")
TPL  = os.path.join(ROOT, "templates")
STATIC = os.path.join(ROOT, "static")

TODAY = datetime.date.today()
YEAR = TODAY.year

# ---------------------------------------------------------------- load data
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

SITE = load_json(os.path.join(DATA, "site.json"))
COMPARES = load_json(os.path.join(DATA, "compares.json"))

# ---- config (non-secret config.json + gitignored config.local.json overlay) ----
def _load_config():
    base_path = os.path.join(ROOT, "config.json")
    base = load_json(base_path) if os.path.exists(base_path) else {}
    local_path = os.path.join(ROOT, "config.local.json")
    if os.path.exists(local_path):
        local = load_json(local_path)
        for k, v in local.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k].update(v)
            else:
                base[k] = v
    return base

CONFIG = _load_config()
TOKENS = {
    "ga4": CONFIG.get("analytics", {}).get("ga4", ""),
    "gsc": CONFIG.get("analytics", {}).get("gsc", ""),
    "bing": CONFIG.get("analytics", {}).get("bing", ""),
}
FORM_ACTION = CONFIG.get("contact", {}).get("form_action", "") or "#"

def aff_url(robo_id):
    a = CONFIG.get("affiliate", {}).get(robo_id, "")
    if a:
        return a
    return CONFIG.get("affiliate_fallback", {}).get(robo_id, "#")

FUNDS = []
FAMILY_ORDER = ["Vanguard", "Fidelity", "Schwab", "T. Rowe Price", "American Funds"]
for fp in sorted(glob.glob(os.path.join(DATA, "funds", "*.json"))):
    FUNDS.extend(load_json(fp))

FUND_BY_TICKER = {f["ticker"]: f for f in FUNDS}

# ---------------------------------------------------------------- data sanity
# Mechanical guards that cannot be fooled by a bad source: if an automated
# audit ever writes an implausible value or drops a required field, the build
# fails here and nothing deploys. Tune ER_MAX if a legitimate fund exceeds it.
ER_MIN, ER_MAX = 0.0, 3.0            # plausible expense-ratio band (%)
MIN_MAX = 100_000_000               # plausible minimum-investment ceiling ($)
VALID_TYPES = {"index", "active", "target-date"}
REQUIRED_FIELDS = ("ticker", "name", "family", "category", "type",
                   "strategy", "best_for", "editorial", "expense_ratio", "minimum")

def validate_data():
    problems = []
    seen = {}
    for f in FUNDS:
        t = f.get("ticker", "<no ticker>")
        for fld in REQUIRED_FIELDS:
            if fld not in f or f[fld] in (None, "", []):
                problems.append(f"{t}: missing/empty required field '{fld}'")
        if t in seen:
            problems.append(f"{t}: duplicate ticker")
        seen[t] = True
        er = f.get("expense_ratio")
        if not isinstance(er, (int, float)) or not (ER_MIN <= er <= ER_MAX):
            problems.append(f"{t}: expense_ratio {er!r} outside [{ER_MIN},{ER_MAX}] — refusing to publish")
        m = f.get("minimum")
        if not isinstance(m, int) or m < 0 or m > MIN_MAX:
            problems.append(f"{t}: minimum {m!r} invalid (int 0..{MIN_MAX})")
        if f.get("type") not in VALID_TYPES:
            problems.append(f"{t}: type {f.get('type')!r} not in {sorted(VALID_TYPES)}")
        ed = f.get("editorial")
        if isinstance(ed, list) and not (1 <= len(ed) <= 4):
            problems.append(f"{t}: editorial has {len(ed)} paragraphs (expected 1-4)")
    # every comparison must reference funds that exist
    for c in COMPARES:
        for side in ("a", "b"):
            if c.get(side) not in FUND_BY_TICKER:
                problems.append(f"compare {c.get('a')}-vs-{c.get('b')}: '{c.get(side)}' is not a known ticker")
    if problems:
        raise SystemExit("DATA VALIDATION FAILED (nothing published):\n  " + "\n  ".join(problems))
    print(f"Data validation OK: {len(FUNDS)} funds, {len(COMPARES)} comparisons, all fields sane")

LAST_VERIFIED = SITE.get("last_verified", TODAY.isoformat())
LV_HUMAN = datetime.date.fromisoformat(LAST_VERIFIED).strftime("%B %-d, %Y")

# ---------------------------------------------------------------- helpers
def er_pct(er):
    if er == 0:
        return "0.00%"
    if round(er, 2) == er:
        return f"{er:.2f}%"
    return f"{er:.3f}%"

def er_class(er):
    if er < 0.10:
        return "er-good"
    if er < 0.50:
        return "er-mid"
    return "er-high"

def cost_10k(er):
    amt = er / 100.0 * 10000.0
    if amt == 0:
        return "$0"
    if abs(amt - round(amt)) < 1e-9:
        return f"${int(round(amt))}"
    return f"${amt:,.2f}"

def min_human(m):
    if m == 0:
        return "$0"
    if m >= 1_000_000:
        return f"${m//1_000_000}M (instit.)"
    return f"${m:,}"

TYPE_HUMAN = {"index": "Index", "active": "Active", "target-date": "Target-Date"}

def type_human(t):
    return TYPE_HUMAN.get(t, t.title())

def slugify_pair(a, b):
    return f"{a.lower()}-vs-{b.lower()}"

def decorate(f):
    """Attach derived display fields to a fund dict (idempotent)."""
    f = dict(f)
    f["er_pct"] = er_pct(f["expense_ratio"])
    f["er_class"] = er_class(f["expense_ratio"])
    f["cost_10k"] = cost_10k(f["expense_ratio"])
    f["min_human"] = min_human(f["minimum"])
    f["type_human"] = type_human(f["type"])
    return f

DEC = {t: decorate(f) for t, f in FUND_BY_TICKER.items()}

# pre-compute slugs on compares + resolve teaser
for c in COMPARES:
    c["slug"] = slugify_pair(c["a"], c["b"])
    # teaser = first sentence of intro
    c["teaser"] = re.split(r"(?<=[.!?])\s", c["intro"].strip())[0]

# ---------------------------------------------------------------- jinja
env = Environment(
    loader=FileSystemLoader(TPL),
    autoescape=select_autoescape(["html", "xml"]),
)

BASE_CTX = {
    "domain": SITE["domain"],
    "site_name": SITE["site_name"],
    "tagline": SITE["tagline"],
    "tokens": TOKENS,
    "nav": SITE["nav"],
    "footer_nav": SITE["footer_nav"],
    "author": SITE["author"],
    "author_initials": "".join(p[0] for p in SITE["author"]["name"].split()[:2]).upper(),
    "last_verified_human": LV_HUMAN,
    "fund_count": len(FUNDS),
    "year": YEAR,
}

PAGES = []  # (url_path, priority) for sitemap

def render(template, out_path, url, ctx, priority="0.6"):
    """Render a template to dist/out_path and record the URL for the sitemap."""
    full_ctx = dict(BASE_CTX)
    full_ctx.update(ctx)
    full_ctx.setdefault("canonical", url)
    html = env.get_template(template).render(**full_ctx)
    dest = os.path.join(DIST, out_path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(html)
    PAGES.append((url, priority))

# ---------------------------------------------------------------- schema builders
def crumb_schema(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name,
             "item": SITE["domain"] + url}
            for i, (name, url) in enumerate(items)
        ],
    }

def article_schema(headline, desc, url):
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": headline,
        "description": desc,
        "datePublished": LAST_VERIFIED,
        "dateModified": LAST_VERIFIED,
        "author": {"@type": "Person", "name": SITE["author"]["name"],
                   "url": SITE["domain"] + SITE["author"]["url"]},
        "publisher": {"@type": "Organization", "name": SITE["site_name"]},
        "mainEntityOfPage": {"@type": "WebPage", "@id": SITE["domain"] + url},
    }

def faq_schema(faqs):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": f["q"],
             "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
            for f in faqs
        ],
    }

# ---------------------------------------------------------------- FAQ generation
def build_faqs(f):
    t = f["ticker"]
    name = f["name"]
    ep = er_pct(f["expense_ratio"])
    c10 = cost_10k(f["expense_ratio"])
    er = f["expense_ratio"]
    # cost framing
    if er == 0:
        cost_note = "That is a zero expense ratio — among the cheapest funds available anywhere."
    elif er < 0.10:
        cost_note = "That is very low by industry standards, where the average fund still charges well over 0.40%."
    elif er < 0.50:
        cost_note = "That is moderate — cheap for an actively managed fund, but several times what a comparable index fund charges."
    else:
        cost_note = "That is high relative to index alternatives, and it compounds against you every year, so the fund needs to outperform just to break even versus a cheaper option."

    # minimum framing
    m = f["minimum"]
    if m == 0:
        min_note = f"{t} has no minimum initial investment — you can start with any amount."
    elif m >= 1_000_000:
        min_note = (f"The institutional share class of {t} carries a $1,000,000 minimum, "
                    "but most retail investors access it inside a 401(k) plan, where the minimum is waived. "
                    "Retail share classes with lower minimums exist at higher fees.")
    else:
        min_note = f"{t} requires a minimum initial investment of ${m:,}."

    # alternatives
    alts = [a for a in f.get("alternatives", []) if a in FUND_BY_TICKER][:3]
    if alts:
        alt_txt = ", ".join(alts)
        alt_note = (f"The funds most often compared with {t} are {alt_txt} — broadly similar exposure "
                    "from different providers, with small differences in fee, minimum, and portability "
                    "that usually come down to which brokerage holds your account.")
    else:
        alt_note = f"{t} is fairly distinctive in its category; see its full review for the closest comparable funds."

    faqs = [
        {"q": f"What is the expense ratio of {t}?",
         "a": f"{t} ({name}) has an expense ratio of {ep}, which works out to roughly {c10} per year for every $10,000 invested. {cost_note}"},
        {"q": f"What is the minimum investment for {t}?",
         "a": min_note},
        {"q": f"What does {t} invest in?",
         "a": f"{f['strategy']} It falls in the {f['category'].lower()} category and is {('an index fund' if f['type']=='index' else 'a target-date fund' if f['type']=='target-date' else 'an actively managed fund')}."},
        {"q": f"What are good alternatives to {t}?",
         "a": alt_note},
    ]
    return faqs

# ---------------------------------------------------------------- render: fund pages
def render_fund(f):
    t = f["ticker"]
    d = DEC[t]
    url = f"/funds/{t.lower()}/"
    alts = [DEC[a] for a in f.get("alternatives", []) if a in DEC]
    related = [c for c in COMPARES if c["a"] == t or c["b"] == t]
    faqs = build_faqs(f)

    desc = (f"{t} review: {f['name']} has a {er_pct(f['expense_ratio'])} expense ratio "
            f"and {min_human(f['minimum'])} minimum. What it holds, what it costs, who it fits, and alternatives.")
    title = f"{t} Review ({YEAR}): Fees, Holdings & Alternatives | Mutual Fund Reviewer"

    json_ld = [
        article_schema(f"{t} Review: {f['name']}", desc, url),
        faq_schema(faqs),
        crumb_schema([("Home", "/"), ("Fund Reviews", "/funds/"), (t, url)]),
    ]

    render("fund.html", os.path.join("funds", t.lower(), "index.html"), url, {
        "fund": d,
        "alternatives": alts,
        "related_compares": related,
        "faqs": faqs,
        "er_pct": d["er_pct"], "er_class": d["er_class"], "cost_10k": d["cost_10k"],
        "min_human": d["min_human"], "type_human": d["type_human"],
        "page_title": title, "meta_desc": desc,
        "og_type": "article", "json_ld": json_ld,
    }, priority="0.8")

# ---------------------------------------------------------------- render: compare pages
def render_compare(c):
    a, b = DEC[c["a"]], DEC[c["b"]]
    url = f"/compare/{c['slug']}/"
    desc = (f"{c['a']} vs {c['b']}: compare expense ratios ({a['er_pct']} vs {b['er_pct']}), "
            f"minimums, strategy, and which fund fits you. A plain-English verdict.")
    title = f"{c['a']} vs {c['b']} ({YEAR}): Which Fund Is Better? | Mutual Fund Reviewer"
    json_ld = [
        article_schema(f"{c['a']} vs {c['b']}", desc, url),
        crumb_schema([("Home", "/"), ("Comparisons", "/compare/"),
                      (f"{c['a']} vs {c['b']}", url)]),
    ]
    render("compare.html", os.path.join("compare", c["slug"], "index.html"), url, {
        "a": a, "b": b, "cmp": c,
        "page_title": title, "meta_desc": desc,
        "og_type": "article", "json_ld": json_ld,
    }, priority="0.7")

# ---------------------------------------------------------------- best-index-funds groups
def best_index_groups():
    cat_blurbs = {
        "Total US Market": "Own every public US company in one fund. For most investors this is the single best core holding in existence — and the funds below are nearly identical.",
        "S&P 500 / Large Blend": "The 500 largest US companies — about 80% of the market by value. The classic benchmark, and the cheapest option in most 401(k) plans.",
        "International": "Everything outside the United States. Whether to own it is debated; if you do, these are the cheap, broad ways to get it.",
        "Bond": "The ballast in a portfolio. Bonds won't make you rich; they keep a bad year from making you panic. These track the broad investment-grade market.",
        "Small Cap": "A deliberate tilt toward smaller US companies. A refinement, not a requirement — your total-market fund already owns these at market weight.",
        "Large Growth": "Indexed exposure to the market's fastest-growing large companies. Concentrated in mega-cap tech by construction — handle as a dial, not a diversifier.",
        "Target-Date": "A complete, self-managing portfolio in one fund, matched to your retirement year. For many savers, the only fund they ever need.",
    }
    order = ["Total US Market", "S&P 500 / Large Blend", "International", "Bond",
             "Small Cap", "Large Growth", "Target-Date"]
    groups = []
    for cat in order:
        funds = [DEC[t] for t, f in FUND_BY_TICKER.items()
                 if f["category"] == cat and f["type"] in ("index", "target-date")]
        funds.sort(key=lambda x: (x["expense_ratio"], x["minimum"], x["ticker"]))
        funds = funds[:8]
        if funds:
            groups.append({"title": cat, "blurb": cat_blurbs.get(cat, ""), "funds": funds})
    return groups

# ---------------------------------------------------------------- static pages content
def legal_pages():
    a = SITE["author"]
    pages = {}

    pages["methodology"] = ("Methodology", "How We Review Funds", f"""
<p class="lead">No secret formula, no proprietary score. Our reviews rest on a few stubborn principles and publicly verifiable facts.</p>
<h2>What we evaluate</h2>
<p><b>Cost first.</b> The expense ratio is the one variable that is knowable in advance and compounds against you with certainty, so it leads every review and drives every ranking. We treat a low fee as the strongest single point in a fund's favor — because, over decades, the evidence says it is.</p>
<p><b>What you actually own.</b> We describe a fund's strategy in plain English — what index it tracks or what an active manager is trying to do — so you understand the exposure, not just the marketing name.</p>
<p><b>Suitability, not hype.</b> Every review names who a fund fits and who it doesn't. A great fund in the wrong account or portfolio is a mistake; we'd rather tell you that than sell you on it.</p>
<p><b>Honest treatment of active funds.</b> We are pro-index, not anti-active. Where an active fund has a genuinely strong, low-cost, well-structured case, we say so plainly — and where it's an expensive bet dressed as expertise, we say that too.</p>
<h2>How we rank "best" funds</h2>
<p>Within a category, we rank primarily by expense ratio, with minimums and structural tie-breakers (portability, index quality, distribution quirks) noted. We do <em>not</em> rank by past returns, because past returns have almost no power to predict future returns, and ranking by them would simply chase last year's luck.</p>
<h2>Where our data comes from</h2>
<p>Expense ratios, minimums, and strategies come from fund providers' own documentation and prospectuses. Every figure carries a last-verified date. Funds change their terms; we re-verify periodically, but you should always confirm against the official prospectus before investing.</p>
<h2>What we don't do</h2>
<p>We don't forecast returns, we don't publish price targets, and we don't tell you what to buy — we are a publication, not your advisor. The only forward-looking number anywhere on this site is in the <a href="/expense-ratio-calculator/">fee calculator</a>, and that is neutral compound-interest math you control entirely.</p>
""")

    pages["how-we-make-money"] = ("How We Make Money", "How We Make Money", f"""
<p class="lead">Plainly, because you deserve to know what's behind a recommendation.</p>
<h2>Two ways, both disclosed</h2>
<p><b>Affiliate partnerships.</b> Some links to brokerages and robo-advisors — on the <a href="/robo-advisors/">robo-advisors</a> page and elsewhere — are affiliate links. If you open an account through one, the company may pay us a commission. It costs you nothing extra.</p>
<p><b>Display advertising.</b> We run display ads on some pages. They're labeled, and they don't influence our editorial.</p>
<h2>What money does not buy here</h2>
<p>It does not buy a rating, a ranking position, or a kinder review. Our rankings are driven by expense ratios and suitability, full stop — and you'll notice we repeatedly point readers toward near-zero-cost index funds we earn nothing from, and openly tell you that the cheapest version of a robo-advisor is doing it yourself. That's the tell that the editorial comes first.</p>
<h2>The inherent tension, named</h2>
<p>Affiliate revenue creates an incentive to send you to partners. We manage it the only honest way: by leading with the cheap, commission-free DIY path on every page where a paid option appears, and by disclosing the relationship every time. If a recommendation ever reads like it's working against your interests, it's a bug — tell us.</p>
""")

    pages["about"] = ("About", "About Mutual Fund Reviewer", f"""
<p class="lead">A small, opinionated publication for long-term investors who'd rather keep their money than feed it to fees.</p>
<p>Mutual Fund Reviewer exists because the gap between "good fund" and "bad fund" is, for most people, mostly about cost — and almost nobody explains that in plain language without trying to sell you something complicated. We review index funds, mutual funds, and the platforms that sell them, with a Bogleheads-adjacent bias: low costs win, hype loses, and the boring portfolio usually wins the race.</p>
<div class="author-box">
  <div class="av">{BASE_CTX['author_initials']}</div>
  <div class="who"><b>{a['name']}</b> &middot; <span class="t">{a['title']}</span>
  <p>{a['bio']}</p></div>
</div>
<h2>What we are not</h2>
<p>We are not financial advisors. {a['name']} is a writer and editor, not a licensed advisor, broker, or tax professional. Nothing on this site is personalized advice — it's general education and editorial opinion, and your situation may call for something different. For advice tailored to you, talk to a fee-only fiduciary.</p>
<h2>How to use this site</h2>
<p>Start with the <a href="/best-index-funds/">best index funds</a> if you want picks, the <a href="/expense-ratio-calculator/">fee calculator</a> if you want a wake-up call, or the <a href="/funds/">full fund directory</a> if you have a specific ticker in mind.</p>
""")

    contact_form = f"""
<p class="lead">Spotted an out-of-date figure? Have a fund you'd like reviewed? We read everything.</p>
<form action="{FORM_ACTION}" method="POST">
  <div class="field"><label for="cname">Your name</label><input type="text" id="cname" name="name" required></div>
  <div class="field"><label for="cemail">Email</label><input type="text" id="cemail" name="email" required></div>
  <div class="field"><label for="cmsg">Message</label><textarea id="cmsg" name="message" rows="6" required style="width:100%;font-family:'Public Sans',sans-serif;font-size:1rem;padding:.6rem .7rem;border:1px solid var(--line-strong);border-radius:5px"></textarea></div>
  <button class="btn btn-gold" type="submit">Send message</button>
</form>
<p class="tiny" style="margin-top:1.2em">We can't provide personalized investment advice and won't tell you what to buy — but corrections, questions, and review requests are always welcome.</p>
"""
    pages["contact"] = ("Contact", "Contact Us", contact_form)

    pages["privacy"] = ("Privacy Policy", "Privacy Policy", f"""
<p>This Privacy Policy explains what information Mutual Fund Reviewer collects and how it is used. By using this site, you consent to the practices described here.</p>
<h2>Information we collect</h2>
<p><b>Analytics.</b> We use Google Analytics to understand how visitors use the site (pages viewed, general location, device type). This data is aggregated and not used to personally identify you.</p>
<p><b>Contact form.</b> If you message us, we collect the name, email, and message you provide, solely to respond.</p>
<p><b>Cookies.</b> We and our analytics and advertising partners use cookies. You can disable cookies in your browser; some features may not work as well.</p>
<h2>Advertising &amp; affiliates</h2>
<p>We display ads and use affiliate links. Advertising partners may use cookies to serve relevant ads. Affiliate partners may set a cookie to attribute a referral; see <a href="/how-we-make-money/">How We Make Money</a>.</p>
<h2>Third parties</h2>
<p>We don't sell your personal information. Third-party services we use (analytics, ad networks, affiliate networks) have their own privacy policies governing the data they collect.</p>
<h2>Your choices</h2>
<p>Depending on your location, you may have rights to access or delete personal data we hold. Contact us via the <a href="/contact/">contact page</a> to make a request.</p>
<h2>Changes</h2>
<p>We may update this policy; the "last updated" date reflects the latest revision.</p>
""")

    pages["terms"] = ("Terms of Use", "Terms of Use", f"""
<p>By accessing Mutual Fund Reviewer, you agree to these Terms of Use. If you do not agree, please do not use the site.</p>
<h2>Editorial content, not advice</h2>
<p>All content is general information and editorial opinion for educational purposes. It is not investment, financial, tax, or legal advice, and it is not a recommendation to buy or sell any security. You are solely responsible for your investment decisions.</p>
<h2>No warranty</h2>
<p>We work to keep information accurate and current, but we make no warranty as to completeness or accuracy. Fund data changes; figures are provided "as is" with last-verified dates, and you must confirm details against official sources before acting.</p>
<h2>Limitation of liability</h2>
<p>To the fullest extent permitted by law, Mutual Fund Reviewer and its author are not liable for any losses or damages arising from your use of the site or reliance on its content.</p>
<h2>External links</h2>
<p>We link to third-party sites, including affiliate partners. We are not responsible for their content or practices.</p>
<h2>Intellectual property</h2>
<p>Site content is owned by Mutual Fund Reviewer unless otherwise noted and may not be reproduced without permission.</p>
""")

    pages["disclaimer"] = ("Disclaimer", "Disclaimer", f"""
<div class="callout"><span class="label">Read this first</span><p>Mutual Fund Reviewer is an independent publication. We are not investment advisors, and nothing here is personalized advice.</p></div>
<h2>Not investment advice</h2>
<p>{a['name']} is a writer and editor, not a licensed financial advisor, registered investment adviser, broker-dealer, or tax professional. All content is general education and editorial opinion. It does not account for your personal financial situation, goals, or risk tolerance, and it is not a recommendation to buy, sell, or hold any security.</p>
<h2>Investing involves risk</h2>
<p>All investing carries risk, including the possible loss of principal. Past performance does not guarantee future results. The expense ratio calculator on this site performs neutral compound-interest arithmetic using assumptions you set; it is illustrative and not a projection or guarantee of any actual return.</p>
<h2>Data accuracy</h2>
<p>Expense ratios, minimums, and fund details come from provider documentation and carry last-verified dates, but they change frequently. Always confirm figures against a fund's official prospectus before investing.</p>
<h2>Affiliate disclosure</h2>
<p>This site contains affiliate links and display advertising. We may earn commissions on qualifying actions at no additional cost to you. See <a href="/how-we-make-money/">How We Make Money</a>. Affiliate relationships never influence our editorial assessments.</p>
<h2>Consult a professional</h2>
<p>For advice tailored to your circumstances, consult a qualified fee-only fiduciary financial advisor and a tax professional.</p>
""")
    return pages

def render_legal():
    pages = legal_pages()
    slug_map = {
        "methodology": "/methodology/", "how-we-make-money": "/how-we-make-money/",
        "about": "/about/", "contact": "/contact/", "privacy": "/privacy/",
        "terms": "/terms/", "disclaimer": "/disclaimer/",
    }
    for slug, (crumb, h1, body) in pages.items():
        url = slug_map[slug]
        title = f"{h1} | Mutual Fund Reviewer"
        desc = f"{h1} — Mutual Fund Reviewer. {('Independent, plain-English fund reviews.' )}"
        json_ld = [
            article_schema(h1, desc, url),
            crumb_schema([("Home", "/"), (crumb, url)]),
        ]
        render("page.html", os.path.join(slug.strip("/"), "index.html"), url, {
            "crumb": crumb, "h1": h1, "body": body, "updated": LV_HUMAN,
            "page_title": title, "meta_desc": desc, "json_ld": json_ld,
        }, priority="0.4")

# ---------------------------------------------------------------- sitemap / robots
def write_sitemap():
    urls = []
    for url, prio in PAGES:
        urls.append(
            f"  <url><loc>{SITE['domain']}{url}</loc>"
            f"<lastmod>{LAST_VERIFIED}</lastmod>"
            f"<priority>{prio}</priority></url>"
        )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(DIST, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)

def write_robots():
    txt = ("User-agent: *\nAllow: /\n\n"
           f"Sitemap: {SITE['domain']}/sitemap.xml\n")
    with open(os.path.join(DIST, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(txt)

# ---------------------------------------------------------------- main build
GUIDE_META_RE = re.compile(r"\{#META(.*?)META#\}", re.S)

def render_guides():
    """Render templates/guides/*.html (each a body partial with a {#META ... META#}
    JSON header) to /guides/<slug>/, plus the /guides/ index. Guide bodies can use
    live fund data via `dec` (decorated funds by ticker) and helpers."""
    gdir = os.path.join(TPL, "guides")
    guides_meta = []
    if os.path.isdir(gdir):
        extra = {"funds": FUNDS, "dec": DEC, "compares": COMPARES,
                 "er_pct": er_pct, "min_human": min_human, "cost_10k": cost_10k}
        for path in sorted(glob.glob(os.path.join(gdir, "*.html"))):
            src = open(path, encoding="utf-8").read()
            m = GUIDE_META_RE.search(src)
            if not m:
                continue
            meta = json.loads(m.group(1).strip())
            body_src = GUIDE_META_RE.sub("", src, count=1).strip()
            slug = meta["slug"]
            url = f"/guides/{slug}/"
            body_ctx = dict(BASE_CTX); body_ctx.update(extra)
            body_html = env.from_string(body_src).render(**body_ctx)
            date = meta.get("date", LAST_VERIFIED)
            try:
                updated_human = datetime.date.fromisoformat(date).strftime("%B %-d, %Y")
            except Exception:
                updated_human = LV_HUMAN
            guide = {"slug": slug, "path": url,
                     "h1": meta.get("h1", meta["title"]),
                     "crumb": meta.get("crumb", meta["title"]),
                     "lede": meta.get("lede", ""),
                     "summary": meta.get("summary", meta.get("meta_desc", "")),
                     "updated_human": updated_human, "date": date}
            json_ld = [article_schema(guide["h1"], meta["meta_desc"], url),
                       crumb_schema([("Home", "/"), ("Guides", "/guides/"),
                                     (guide["crumb"], url)])]
            if meta.get("faqs"):
                json_ld.append(faq_schema(meta["faqs"]))
            render("guide.html", os.path.join("guides", slug, "index.html"), url, {
                "guide": guide, "body": body_html,
                "page_title": meta["title"], "meta_desc": meta["meta_desc"],
                "og_type": "article", "json_ld": json_ld,
            }, priority="0.7")
            guides_meta.append(guide)
    render("guides-index.html", os.path.join("guides", "index.html"), "/guides/", {
        "guides": guides_meta,
        "page_title": "Investing Guides for Long-Term Index Investors | Mutual Fund Reviewer",
        "meta_desc": ("Plain-English guides to expense ratios, index-fund portfolios, "
                      "account types, and the math that actually moves your retirement."),
        "json_ld": [crumb_schema([("Home", "/"), ("Guides", "/guides/")])],
    }, priority="0.6")
    return guides_meta

def build_guard():
    """Fail the build if any uppercase {{TOKEN}} placeholder leaked into output,
    or if the page count is implausibly low (a sign something didn't render)."""
    problems = []
    html_files = glob.glob(os.path.join(DIST, "**", "*.html"), recursive=True)
    tok = re.compile(r"\{\{\s*[A-Z0-9_]+\s*\}\}")
    for p in html_files:
        if tok.search(open(p, encoding="utf-8").read()):
            problems.append(f"{os.path.relpath(p, DIST)}: leftover uppercase {{TOKEN}}")
    n = len(html_files)
    if n < 140:
        problems.append(f"only {n} HTML pages built (expected >=140)")
    if problems:
        raise SystemExit("BUILD GUARD FAILED:\n  " + "\n  ".join(problems))
    print(f"Build guard OK: {n} pages, no leftover tokens")

def main():
    validate_data()   # refuse to publish implausible or incomplete data
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    # static
    shutil.copytree(STATIC, os.path.join(DIST, "static"))

    # featured funds for home (well-known tickers)
    featured_tickers = ["VTSAX", "FXAIX", "FZROX", "VTIAX", "VBTLX", "VFIFX",
                        "FCNTX", "VWELX", "DODGX", "AGTHX"]
    featured = [DEC[t] for t in featured_tickers if t in DEC]
    featured_compares = COMPARES[:8]

    # ---- homepage
    home_ld = [
        {"@context": "https://schema.org", "@type": "WebSite",
         "name": SITE["site_name"], "url": SITE["domain"],
         "publisher": {"@type": "Organization", "name": SITE["site_name"]}},
        {"@context": "https://schema.org", "@type": "Organization",
         "name": SITE["site_name"], "url": SITE["domain"]},
    ]
    render("home.html", "index.html", "/", {
        "featured": featured, "featured_compares": featured_compares,
        "page_title": "Mutual Fund Reviewer — Plain-English Index & Mutual Fund Reviews",
        "meta_desc": (f"Independent, plain-English reviews of {len(FUNDS)} index funds, mutual funds, "
                      "and robo-advisors for long-term investors. Low costs win, hype loses."),
        "json_ld": home_ld,
    }, priority="1.0")

    # ---- best index funds
    render("best-index-funds.html", os.path.join("best-index-funds", "index.html"),
           "/best-index-funds/", {
        "groups": best_index_groups(),
        "page_title": f"Best Index Funds {YEAR}: Ranked by Expense Ratio | Mutual Fund Reviewer",
        "meta_desc": ("The best index funds by category — total market, S&P 500, international, bonds, "
                      "and target-date — ranked by expense ratio. Plain-English picks for long-term investors."),
        "json_ld": [article_schema(f"Best Index Funds {YEAR}",
                    "The best index funds by category, ranked by expense ratio.",
                    "/best-index-funds/"),
                    crumb_schema([("Home", "/"), ("Best Index Funds", "/best-index-funds/")])],
    }, priority="0.9")

    # ---- calculator
    render("calculator.html", os.path.join("expense-ratio-calculator", "index.html"),
           "/expense-ratio-calculator/", {
        "page_title": "Expense Ratio Calculator: What Fund Fees Cost Over 30 Years",
        "meta_desc": ("Free expense ratio calculator. See what the difference between a low-fee and high-fee "
                      "fund really costs over decades — interactive, with a growth chart."),
        "json_ld": [article_schema("Expense Ratio Calculator",
                    "See what fund fees cost over time.",
                    "/expense-ratio-calculator/"),
                    crumb_schema([("Home", "/"), ("Expense Ratio Calculator", "/expense-ratio-calculator/")])],
    }, priority="0.9")

    # ---- index vs active
    render("index-vs-active.html", os.path.join("index-vs-active", "index.html"),
           "/index-vs-active/", {
        "page_title": "Index vs. Active Funds: What the Data Actually Says | Mutual Fund Reviewer",
        "meta_desc": ("Do active fund managers beat the index? The decades of evidence, presented fairly — "
                      "including where active management genuinely has a case."),
        "json_ld": [article_schema("Index vs. Active: What the Data Actually Says",
                    "The evidence on active versus passive fund management.",
                    "/index-vs-active/"),
                    crumb_schema([("Home", "/"), ("Index vs. Active", "/index-vs-active/")])],
    }, priority="0.7")

    # ---- target date
    render("target-date-funds.html", os.path.join("target-date-funds", "index.html"),
           "/target-date-funds/", {
        "page_title": "Target-Date Funds: How to Pick One | Mutual Fund Reviewer",
        "meta_desc": ("How to choose a target-date fund: insist on the index version, match the date to your "
                      "timeline, and hold it as your whole account. Plus the major series compared."),
        "json_ld": [article_schema("Target-Date Funds: How to Pick One",
                    "A guide to choosing a target-date retirement fund.",
                    "/target-date-funds/"),
                    crumb_schema([("Home", "/"), ("Target-Date Funds", "/target-date-funds/")])],
    }, priority="0.7")

    # ---- robo advisors (resolve affiliate URL per robo from config)
    robos_dec = []
    for r in SITE["robos"]:
        rr = dict(r)
        rr["url"] = aff_url(r["id"])
        robos_dec.append(rr)
    render("robo-advisors.html", os.path.join("robo-advisors", "index.html"),
           "/robo-advisors/", {
        "robos": robos_dec,
        "page_title": "Robo-Advisors Reviewed: The Honest Trade-Off | Mutual Fund Reviewer",
        "meta_desc": ("Betterment, Wealthfront, M1, Interactive Brokers, and SoFi reviewed for long-term "
                      "investors — with the DIY-is-cheaper trade-off front and center."),
        "json_ld": [article_schema("Robo-Advisors Reviewed",
                    "Honest reviews of the major robo-advisors and brokers.",
                    "/robo-advisors/"),
                    crumb_schema([("Home", "/"), ("Robo-Advisors", "/robo-advisors/")])],
    }, priority="0.7")

    # ---- fund directory
    families = []
    seen = set()
    fam_names = FAMILY_ORDER + sorted({f["family"] for f in FUNDS} - set(FAMILY_ORDER))
    for fam in fam_names:
        fl = [DEC[f["ticker"]] for f in FUNDS if f["family"] == fam]
        fl.sort(key=lambda x: (x["category"], x["ticker"]))
        if fl:
            families.append({"name": fam, "funds": fl})
            seen.add(fam)
    render("funds-index.html", os.path.join("funds", "index.html"), "/funds/", {
        "families": families,
        "page_title": f"All {len(FUNDS)} Fund Reviews | Mutual Fund Reviewer",
        "meta_desc": f"Browse all {len(FUNDS)} fund reviews — Vanguard, Fidelity, Schwab, T. Rowe Price, "
                     "American Funds and more — grouped by family, with expense ratios.",
        "json_ld": [crumb_schema([("Home", "/"), ("Fund Reviews", "/funds/")])],
    }, priority="0.8")

    # ---- compare directory
    render("compare-index.html", os.path.join("compare", "index.html"), "/compare/", {
        "compares": COMPARES,
        "page_title": "Fund Comparisons: The Classic Match-Ups | Mutual Fund Reviewer",
        "meta_desc": "VTSAX vs FZROX, FXAIX vs VFIAX, and more — head-to-head fund comparisons with "
                     "expense ratios, minimums, and a plain-English verdict.",
        "json_ld": [crumb_schema([("Home", "/"), ("Comparisons", "/compare/")])],
    }, priority="0.8")

    # ---- programmatic
    for f in FUNDS:
        render_fund(f)
    for c in COMPARES:
        render_compare(c)

    # ---- guides
    guides = render_guides()

    # ---- legal/static
    render_legal()

    # ---- sitemap + robots
    write_sitemap()
    write_robots()

    print(f"Built {len(PAGES)} pages -> {DIST}")
    print(f"  {len(FUNDS)} fund pages, {len(COMPARES)} comparisons, {len(guides)} guides")

    # ---- guardrail (mirrors the GitHub Action check)
    build_guard()

if __name__ == "__main__":
    main()
