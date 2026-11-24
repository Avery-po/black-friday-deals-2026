#!/usr/bin/env python3
"""Parse README.md and generate a static HTML site for GitHub Pages."""

import re
import sys
from pathlib import Path
from html import escape
from datetime import date


def parse_readme(text):
    """Extract categories and deals from the README markdown."""
    categories = []
    current_cat = None
    current_sub = None
    current_rows = []

    for line in text.splitlines():
        # Main category: ## emoji Name
        m = re.match(r'^## (.+)$', line)
        if m:
            if current_cat and current_rows:
                sub_name = current_sub or ""
                current_cat["tables"].append({"subtitle": sub_name, "rows": current_rows})
                current_rows = []
            if current_cat:
                categories.append(current_cat)
            title = m.group(1).strip()
            current_cat = {"title": title, "id": slugify(title), "tables": []}
            current_sub = None
            continue

        # Subcategory: ### Name
        m = re.match(r'^### (.+)$', line)
        if m and current_cat:
            if current_rows:
                sub_name = current_sub or ""
                current_cat["tables"].append({"subtitle": sub_name, "rows": current_rows})
                current_rows = []
            current_sub = m.group(1).strip()
            continue

        # Table row
        if line.startswith('|') and current_cat:
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 4 and cells[0] != 'Product' and cells[0] != 'Retailer' and not all(c.startswith('-') for c in cells):
                # Skip separator rows
                if re.match(r'^[-:\s|]+$', line):
                    continue
                row = parse_deal_row(cells)
                if row:
                    current_rows.append(row)

    if current_cat and current_rows:
        sub_name = current_sub or ""
        current_cat["tables"].append({"subtitle": sub_name, "rows": current_rows})
    if current_cat:
        categories.append(current_cat)

    return categories


def parse_deal_row(cells):
    """Parse a table row into a deal dict."""
    if len(cells) < 4:
        return None

    name_cell = cells[0]
    desc = cells[1] if len(cells) > 1 else ""
    deal = cells[2] if len(cells) > 2 else ""
    status = cells[3] if len(cells) > 3 else ""

    # Extract link and name
    link_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', name_cell)
    if link_match:
        name = link_match.group(1)
        url = link_match.group(2)
    else:
        name = re.sub(r'~~(.+?)~~', r'\1', name_cell).strip()
        url = ""

    # Determine status
    expired = '~~' in name_cell or 'EXPIRED' in deal
    if '✅' in status:
        status_type = 'confirmed'
    elif '⏳' in status:
        status_type = 'expected'
    elif expired or '❌' in status:
        status_type = 'expired'
    else:
        status_type = 'info'

    region = "global"
    audience = "everyone"
    deal_raw = cells[2] if len(cells) > 2 else ""
    if '\U0001f1fa\U0001f1f8' in deal_raw:
        region = "us"
    elif '\U0001f1ec\U0001f1e7' in deal_raw:
        region = "uk"
    elif '\U0001f1ee\U0001f1f3' in deal_raw:
        region = "in"
    elif '\U0001f1e8\U0001f1e6' in deal_raw:
        region = "ca"
    elif '\U0001f1ea\U0001f1fa' in deal_raw:
        region = "eu"
    elif '\U0001f1e9\U0001f1ea' in deal_raw:
        region = "de"
    elif '\U0001f1e6\U0001f1fa' in deal_raw:
        region = "au"
    if '\U0001f393' in deal_raw:
        audience = "student"

    return {
        "name": re.sub(r'~~(.+?)~~', r'\1', name).strip(),
        "url": url,
        "description": clean_md(desc),
        "deal": clean_md(deal),
        "status": status_type,
        "expired": expired,
        "region": region,
        "audience": audience,
    }


def clean_md(text):
    """Convert basic markdown to HTML."""
    text = escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def slugify(text):
    """Create a URL-safe slug."""
    text = re.sub(r'[^\w\s-]', '', text.lower())
    return re.sub(r'[\s]+', '-', text).strip('-')


def count_deals(categories):
    confirmed = 0
    expected = 0
    total = 0
    skip_titles = ('retailer', 'contributing', 'past years', 'table of contents')
    seen = set()
    for cat in categories:
        if any(s in cat['title'].lower() for s in skip_titles):
            continue
        for table in cat["tables"]:
            for row in table["rows"]:
                key = row["name"].lower().strip()
                if key in seen:
                    continue
                seen.add(key)
                total += 1
                if row["status"] == "confirmed":
                    confirmed += 1
                elif row["status"] == "expected":
                    expected += 1
    return total, confirmed, expected


def generate_html(categories):
    total, confirmed, expected = count_deals(categories)
    today = date.today().strftime("%B %d, %Y")

    cat_nav = ""
    cat_tiles = ""
    cat_sections = ""
    skip_titles = ('retailer', 'contributing', 'past years', 'table of contents')
    global_seen = set()

    for cat in categories:
        if any(s in cat['title'].lower() for s in skip_titles):
            continue

        emoji_match = re.match(r'^(\S+)\s+(.+)$', cat['title'])
        if emoji_match:
            emoji = emoji_match.group(1)
            name = emoji_match.group(2)
        else:
            emoji = ""
            name = cat['title']

        cat_count = 0
        for t in cat["tables"]:
            for r in t["rows"]:
                key = r["name"].lower().strip()
                if key not in global_seen:
                    cat_count += 1
                    global_seen.add(key)
        cat_nav += f'<a href="#{cat["id"]}" class="nav-chip">{emoji} {name} <span class="chip-count">{cat_count}</span></a>\n'
        cat_tiles += f'<button class="cat-tile" data-cat="{cat["id"]}"><span class="tile-emoji">{emoji}</span><span class="tile-name">{escape(name)}</span><span class="tile-count">{cat_count} deals</span></button>\n'

        tables_html = ""
        for table in cat["tables"]:
            if not table["rows"]:
                continue
            sub_heading = ""
            if table["subtitle"] and not table["subtitle"].startswith("No BF"):
                clean_sub = re.sub(r'^[^\w]*', '', table["subtitle"]).strip()
                if clean_sub:
                    sub_heading = f'<h3 class="sub-heading">{escape(table["subtitle"])}</h3>'

            if "No BF" in table.get("subtitle", ""):
                note_text = clean_md(table["subtitle"])
                tables_html += f'<div class="no-deal-note">{note_text}</div>'
                continue

            rows_html = ""
            for row in table["rows"]:
                status_class = row["status"]
                status_labels = {
                    "confirmed": "Confirmed",
                    "expected": "Expected",
                    "expired": "Expired",
                    "info": "Info",
                }
                status_label = status_labels.get(row["status"], "")

                name_html = f'<a href="{escape(row["url"])}" target="_blank" rel="noopener">{escape(row["name"])}</a>' if row["url"] else escape(row["name"])
                expired_class = ' expired-row' if row["expired"] else ''

                rows_html += f'''<div class="deal-card{expired_class}" data-status="{status_class}" data-region="{row["region"]}" data-audience="{row["audience"]}">
  <div class="deal-top">
    <div class="deal-name">{name_html}</div>
    <span class="status-badge status-{status_class}">{status_label}</span>
  </div>
  <div class="deal-desc">{row["description"]}</div>
  <div class="deal-price">{row["deal"]}</div>
</div>
'''

            tables_html += f'{sub_heading}<div class="deal-grid">{rows_html}</div>'

        cat_sections += f'''<section id="{cat["id"]}" class="category-section" data-cat="{cat["id"]}">
  <h2 class="cat-title">{escape(cat["title"])}</h2>
  {tables_html}
</section>
'''

    return HTML_TEMPLATE.replace("{{TILES}}", cat_tiles) \
                        .replace("{{NAV_CHIPS}}", cat_nav) \
                        .replace("{{SECTIONS}}", cat_sections) \
                        .replace("{{TOTAL}}", str(total)) \
                        .replace("{{CONFIRMED}}", str(confirmed)) \
                        .replace("{{EXPECTED}}", str(expected)) \
                        .replace("{{DATE}}", today) \
                        .replace("{{CATEGORIES}}", str(len([c for c in categories if not any(s in c['title'].lower() for s in ('retailer', 'contributing', 'past years', 'table of contents'))]))) \
                        .replace("{{ISO_DATE}}", date.today().isoformat())


HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Black Friday & Cyber Monday 2026 Deals — 300+ Curated Deals</title>
<meta name="description" content="The largest curated collection of Black Friday & Cyber Monday 2026 deals. 300+ verified deals across 12 categories for developers, designers, security pros, gamers & more. Updated daily.">
<meta name="keywords" content="black friday 2026, cyber monday 2026, black friday deals, developer deals, cybersecurity deals, saas deals, gaming deals, tech deals, cloud hosting deals, AI tools deals">
<meta name="author" content="Shashankt255">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://shashankt255.github.io/black-friday-deals-2026/">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:title" content="Black Friday & Cyber Monday 2026 Deals — 300+ Curated">
<meta property="og:description" content="300+ verified deals across 12 categories. Dev tools, cybersecurity, cloud, AI, gaming, hardware & more. No affiliate links. Updated daily.">
<meta property="og:url" content="https://shashankt255.github.io/black-friday-deals-2026/">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Black Friday & Cyber Monday 2026 Deals — 300+ Curated">
<meta name="twitter:description" content="300+ verified deals across 12 categories. No affiliate links. Updated daily through Cyber Monday.">

<!-- JSON-LD Structured Data -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Black Friday & Cyber Monday 2026 Deals",
  "description": "The largest curated collection of Black Friday and Cyber Monday 2026 deals with 300+ verified deals across 12 categories.",
  "url": "https://shashankt255.github.io/black-friday-deals-2026/",
  "dateModified": "{{ISO_DATE}}",
  "author": {"@type": "Person", "name": "Shashankt255", "url": "https://github.com/Shashankt255"}
}
</script>

<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap">

<style>
:root {
  --bg: #f7f6f3; --bg-raised: #ffffff; --bg-inset: #eeedea;
  --fg: #1a1917; --fg-2: #4a4740; --fg-3: #8a8780;
  --border: #dddbd6; --border-light: #eeedea;
  --accent: #e04e1a; --accent-hover: #c94516;
  --confirmed: #16a34a; --confirmed-bg: #dcfce7;
  --expected: #d97706; --expected-bg: #fef3c7;
  --expired: #9ca3af; --expired-bg: #f3f4f6;
  --info: #6b7280; --info-bg: #f3f4f6;
  --font: 'Inter', system-ui, -apple-system, sans-serif;
  --mono: 'JetBrains Mono', ui-monospace, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #111110; --bg-raised: #1c1b19; --bg-inset: #161614;
    --fg: #e8e6e1; --fg-2: #b0ada6; --fg-3: #6b6860;
    --border: #2a2924; --border-light: #222120;
    --accent: #f0713a; --accent-hover: #f58a5a;
    --confirmed: #4ade80; --confirmed-bg: #14532d;
    --expected: #fbbf24; --expected-bg: #422006;
    --expired: #6b7280; --expired-bg: #1f2937;
    --info: #9ca3af; --info-bg: #1f2937;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #111110; --bg-raised: #1c1b19; --bg-inset: #161614;
  --fg: #e8e6e1; --fg-2: #b0ada6; --fg-3: #6b6860;
  --border: #2a2924; --border-light: #222120;
  --accent: #f0713a; --accent-hover: #f58a5a;
  --confirmed: #4ade80; --confirmed-bg: #14532d;
  --expected: #fbbf24; --expected-bg: #422006;
  --expired: #6b7280; --expired-bg: #1f2937;
  --info: #9ca3af; --info-bg: #1f2937;
  color-scheme: dark;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; }
body {
  background: var(--bg); color: var(--fg);
  font-family: var(--font); line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

.container {
  max-width: 960px; margin: 0 auto;
  padding: 0 max(20px, env(safe-area-inset-left, 0px));
  padding-right: max(20px, env(safe-area-inset-right, 0px));
}

/* Hero */
.hero {
  padding: 3rem 0 2rem; text-align: center;
}
.hero h1 {
  font-size: clamp(1.75rem, 4vw, 2.5rem); font-weight: 800;
  letter-spacing: -0.03em; text-wrap: balance;
  line-height: 1.15; margin-bottom: 0.75rem;
}
.hero h1 .accent { color: var(--accent); }
.hero-sub {
  font-size: 1.05rem; color: var(--fg-2); max-width: 540px;
  margin: 0 auto 1.5rem; text-wrap: balance;
}
.hero-date {
  font-size: 0.85rem; color: var(--fg-3); margin-bottom: 1.5rem;
}

/* Stats row */
.stats {
  display: flex; gap: 1rem; justify-content: center;
  flex-wrap: wrap; margin-bottom: 2rem;
}
.stat-card {
  background: var(--bg-raised); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.75rem 1.25rem;
  text-align: center; min-width: 120px;
}
.stat-num {
  font-size: 1.5rem; font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.stat-num.green { color: var(--confirmed); }
.stat-num.amber { color: var(--expected); }
.stat-label { font-size: 0.75rem; color: var(--fg-3); text-transform: uppercase; letter-spacing: 0.05em; }

/* GitHub CTA */
.gh-cta {
  display: inline-flex; align-items: center; gap: 0.5rem;
  background: var(--fg); color: var(--bg);
  font-family: var(--font); font-size: 0.9rem; font-weight: 600;
  padding: 0.65rem 1.5rem; border-radius: 8px;
  text-decoration: none; transition: opacity 0.15s;
  margin-bottom: 2rem;
}
.gh-cta:hover { opacity: 0.85; }
.gh-cta svg { width: 18px; height: 18px; fill: currentColor; }

/* Search */
.search-bar {
  position: sticky; top: 0; z-index: 10;
  background: var(--bg); padding: 0.75rem 0;
  border-bottom: 1px solid var(--border-light);
}
.search-input {
  width: 100%; padding: 0.65rem 1rem 0.65rem 2.5rem;
  font-family: var(--font); font-size: 0.9rem;
  background: var(--bg-raised); color: var(--fg);
  border: 1px solid var(--border); border-radius: 8px;
  outline: none; transition: border-color 0.15s;
}
.search-input:focus { border-color: var(--accent); }
.search-input::placeholder { color: var(--fg-3); }
.search-wrap { position: relative; }
.search-icon {
  position: absolute; left: 0.8rem; top: 50%; transform: translateY(-50%);
  width: 16px; height: 16px; color: var(--fg-3); pointer-events: none;
}

/* Filter bar */
.filter-row {
  display: flex; gap: 0.5rem; align-items: center;
  padding: 0.5rem 0; flex-wrap: wrap;
}
.filter-btn {
  font-family: var(--font); font-size: 0.78rem; font-weight: 500;
  padding: 0.3rem 0.75rem; border-radius: 20px; cursor: pointer;
  border: 1px solid var(--border); background: var(--bg-raised); color: var(--fg-2);
  transition: all 0.15s;
}
.filter-btn:hover { border-color: var(--fg-3); }
.filter-btn.active { background: var(--fg); color: var(--bg); border-color: var(--fg); }
.filter-select {
  font-family: var(--font); font-size: 0.78rem; font-weight: 500;
  padding: 0.3rem 0.6rem; border-radius: 20px; cursor: pointer;
  border: 1px solid var(--border); background: var(--bg-raised); color: var(--fg-2);
  appearance: none; -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%238a8780'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 0.5rem center;
  padding-right: 1.4rem; transition: all 0.15s;
}
.filter-select:hover { border-color: var(--fg-3); }
.filter-select:focus { border-color: var(--accent); outline: none; }
.result-count { font-size: 0.78rem; color: var(--fg-3); margin-left: auto; }

/* Category nav chips */
.cat-nav {
  display: flex; gap: 0.4rem; flex-wrap: wrap;
  padding: 0.75rem 0 1.5rem; border-bottom: 1px solid var(--border-light);
  margin-bottom: 1.5rem;
}
.nav-chip {
  font-size: 0.78rem; font-weight: 500; padding: 0.3rem 0.65rem;
  border-radius: 6px; background: var(--bg-inset); color: var(--fg-2);
  text-decoration: none; white-space: nowrap; transition: all 0.15s;
}
.nav-chip:hover { background: var(--border); color: var(--fg); }
.chip-count {
  font-size: 0.65rem; font-weight: 600; color: var(--fg-3);
  margin-left: 0.15rem;
}

/* Category sections */
.category-section { margin-bottom: 2.5rem; }
.cat-title {
  font-size: 1.35rem; font-weight: 700; margin-bottom: 1rem;
  padding-bottom: 0.5rem; border-bottom: 2px solid var(--border-light);
}
.sub-heading {
  font-size: 0.95rem; font-weight: 600; color: var(--fg-2);
  margin: 1.25rem 0 0.75rem;
}

/* Deal cards */
.deal-grid {
  display: grid; gap: 0.5rem;
}
.deal-card {
  background: var(--bg-raised); border: 1px solid var(--border-light);
  border-radius: 8px; padding: 0.75rem 1rem;
  transition: border-color 0.15s;
}
.deal-card:hover { border-color: var(--border); }
.deal-card.expired-row { opacity: 0.55; }
.deal-card[hidden] { display: none !important; }
.deal-top {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 0.5rem; margin-bottom: 0.25rem;
}
.deal-name {
  font-size: 0.9rem; font-weight: 600;
}
.deal-name a {
  color: var(--fg); text-decoration: none;
}
.deal-name a:hover { color: var(--accent); }
.deal-desc {
  font-size: 0.8rem; color: var(--fg-3); margin-bottom: 0.3rem;
}
.deal-price {
  font-size: 0.85rem; color: var(--fg-2);
}
.deal-price strong { color: var(--accent); font-weight: 600; }

/* Status badges */
.status-badge {
  font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em; padding: 0.15rem 0.5rem;
  border-radius: 4px; white-space: nowrap; flex-shrink: 0;
}
.status-confirmed { background: var(--confirmed-bg); color: var(--confirmed); }
.status-expected { background: var(--expected-bg); color: var(--expected); }
.status-expired { background: var(--expired-bg); color: var(--expired); }
.status-info { background: var(--info-bg); color: var(--info); }

.no-deal-note {
  font-size: 0.85rem; color: var(--fg-3); padding: 0.75rem;
  background: var(--bg-inset); border-radius: 6px; margin: 0.5rem 0;
}

/* Tile picker */
.tile-section {
  margin-bottom: 0.5rem;
}
.tile-heading {
  font-size: 0.85rem; font-weight: 600; color: var(--fg-3);
  text-transform: uppercase; letter-spacing: 0.06em;
  margin-bottom: 0.75rem;
}
.tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.5rem; margin-bottom: 0.75rem;
}
.cat-tile {
  display: flex; flex-direction: column; align-items: center;
  gap: 0.15rem; padding: 0.75rem 0.5rem;
  background: var(--bg-raised); border: 2px solid var(--border-light);
  border-radius: 10px; cursor: pointer;
  transition: all 0.15s; font-family: var(--font);
  text-align: center;
}
.cat-tile:hover { border-color: var(--accent); transform: translateY(-1px); }
.cat-tile.selected {
  border-color: var(--accent); background: color-mix(in srgb, var(--accent) 8%, var(--bg-raised));
  box-shadow: 0 0 0 1px var(--accent);
}
.tile-emoji { font-size: 1.5rem; line-height: 1; }
.tile-name { font-size: 0.75rem; font-weight: 600; color: var(--fg); line-height: 1.2; }
.tile-count { font-size: 0.65rem; color: var(--fg-3); }
.tile-clear {
  font-family: var(--font); font-size: 0.75rem; font-weight: 500;
  color: var(--accent); background: none; border: none;
  cursor: pointer; padding: 0.25rem 0;
}
.tile-clear:hover { text-decoration: underline; }

@media (max-width: 600px) {
  .tile-grid { grid-template-columns: repeat(3, 1fr); gap: 0.4rem; }
  .cat-tile { padding: 0.6rem 0.3rem; }
  .tile-emoji { font-size: 1.25rem; }
  .tile-name { font-size: 0.7rem; }
}

/* Footer */
footer {
  text-align: center; padding: 2rem 0 3rem;
  border-top: 1px solid var(--border-light);
  font-size: 0.8rem; color: var(--fg-3);
}
footer a { color: var(--accent); text-decoration: none; }
footer a:hover { text-decoration: underline; }
.footer-links { display: flex; gap: 1.5rem; justify-content: center; margin-bottom: 0.5rem; }

.no-results {
  text-align: center; padding: 3rem 1rem; color: var(--fg-3);
}
.no-results-title { font-size: 1.1rem; font-weight: 600; color: var(--fg-2); margin-bottom: 0.25rem; }

@media (max-width: 600px) {
  .hero { padding: 2rem 0 1.5rem; }
  .hero h1 { font-size: 1.5rem; }
  .stats { gap: 0.5rem; }
  .stat-card { min-width: 90px; padding: 0.5rem 0.75rem; }
  .stat-num { font-size: 1.25rem; }
  .cat-title { font-size: 1.15rem; }
}
</style>
</head>
<body>

<div class="container">
  <div class="hero">
    <h1>Black Friday <span class="accent">&amp;</span> Cyber Monday<br>2026 Deals</h1>
    <p class="hero-sub">The largest curated collection &mdash; {{TOTAL}} verified deals across {{CATEGORIES}} categories. No affiliate links.</p>
    <p class="hero-date">Black Friday: November 27 &bull; Cyber Monday: November 30 &bull; Updated {{DATE}}</p>

    <div class="stats">
      <div class="stat-card">
        <div class="stat-num">{{TOTAL}}</div>
        <div class="stat-label">Total Deals</div>
      </div>
      <div class="stat-card">
        <div class="stat-num green">{{CONFIRMED}}</div>
        <div class="stat-label">Confirmed</div>
      </div>
      <div class="stat-card">
        <div class="stat-num amber">{{EXPECTED}}</div>
        <div class="stat-label">Expected</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{CATEGORIES}}</div>
        <div class="stat-label">Categories</div>
      </div>
    </div>

    <a href="https://github.com/Shashankt255/black-friday-deals-2026" target="_blank" rel="noopener" class="gh-cta">
      <svg viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
      Star on GitHub
    </a>

    <div class="tile-section">
      <p class="tile-heading">Pick your interests</p>
      <div class="tile-grid">
        {{TILES}}
      </div>
      <button class="tile-clear" id="clearTiles" hidden>Clear selection</button>
    </div>
  </div>

  <div class="search-bar">
    <div class="search-wrap">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input type="text" class="search-input" id="search" placeholder="Search deals... (e.g. NordVPN, hosting, OSCP)" autocomplete="off">
    </div>
    <div class="filter-row">
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="confirmed">Confirmed</button>
      <button class="filter-btn" data-filter="expected">Expected</button>
      <select class="filter-select" id="regionFilter">
        <option value="all">All Regions</option>
        <option value="global">🌍 Global</option>
        <option value="us">🇺🇸 US</option>
        <option value="uk">🇬🇧 UK</option>
        <option value="in">🇮🇳 India</option>
        <option value="ca">🇨🇦 Canada</option>
        <option value="eu">🇪🇺 EU</option>
        <option value="de">🇩🇪 Germany</option>
        <option value="au">🇦🇺 Australia</option>
      </select>
      <select class="filter-select" id="audienceFilter">
        <option value="all">Everyone</option>
        <option value="student">🎓 Student / Edu</option>
      </select>
      <span class="result-count" id="resultCount"></span>
    </div>
  </div>

  <nav class="cat-nav">
    {{NAV_CHIPS}}
  </nav>

  <main id="deals">
    {{SECTIONS}}
  </main>

  <div class="no-results" id="noResults" hidden>
    <div class="no-results-title">No deals found</div>
    <p>Try a different search term or filter.</p>
  </div>

  <footer>
    <div class="footer-links">
      <a href="https://github.com/Shashankt255/black-friday-deals-2026">GitHub Repo</a>
      <a href="https://github.com/Shashankt255/black-friday-deals-2026/blob/main/CONTRIBUTING.md">Submit a Deal</a>
      <a href="https://github.com/Shashankt255/glasscage">GLASSCAGE</a>
    </div>
    <p>Updated {{DATE}} &bull; No affiliate links &bull; Maintained by <a href="https://github.com/Shashankt255">Shashankt255</a></p>
  </footer>
</div>

<script>
const search = document.getElementById('search');
const filterBtns = document.querySelectorAll('.filter-btn');
const regionFilter = document.getElementById('regionFilter');
const audienceFilter = document.getElementById('audienceFilter');
const deals = document.querySelectorAll('.deal-card');
const sections = document.querySelectorAll('.category-section');
const noResults = document.getElementById('noResults');
const resultCount = document.getElementById('resultCount');
const tiles = document.querySelectorAll('.cat-tile');
const clearTilesBtn = document.getElementById('clearTiles');
let activeFilter = 'all';
let selectedCats = new Set();

tiles.forEach(tile => {
  tile.addEventListener('click', () => {
    const cat = tile.dataset.cat;
    if (selectedCats.has(cat)) {
      selectedCats.delete(cat);
      tile.classList.remove('selected');
    } else {
      selectedCats.add(cat);
      tile.classList.add('selected');
    }
    clearTilesBtn.hidden = selectedCats.size === 0;
    applyFilters();
  });
});

clearTilesBtn.addEventListener('click', () => {
  selectedCats.clear();
  tiles.forEach(t => t.classList.remove('selected'));
  clearTilesBtn.hidden = true;
  applyFilters();
});

function applyFilters() {
  const q = search.value.toLowerCase().trim();
  const region = regionFilter.value;
  const audience = audienceFilter.value;
  const hasCatFilter = selectedCats.size > 0;
  let visible = 0;

  sections.forEach(sec => {
    const catMatch = !hasCatFilter || selectedCats.has(sec.dataset.cat);
    sec.querySelectorAll('.deal-card').forEach(card => {
      const text = card.textContent.toLowerCase();
      const status = card.dataset.status;
      const cardRegion = card.dataset.region;
      const cardAudience = card.dataset.audience;
      const matchSearch = !q || text.includes(q);
      const matchStatus = activeFilter === 'all' || status === activeFilter;
      const matchRegion = region === 'all' || cardRegion === region;
      const matchAudience = audience === 'all' || cardAudience === audience;
      const show = catMatch && matchSearch && matchStatus && matchRegion && matchAudience;
      card.hidden = !show;
      if (show) visible++;
    });
    const anyVisible = Array.from(sec.querySelectorAll('.deal-card')).some(c => !c.hidden);
    sec.hidden = !anyVisible;
  });

  noResults.hidden = visible > 0;
  const hasFilter = q || activeFilter !== 'all' || region !== 'all' || audience !== 'all' || hasCatFilter;
  resultCount.textContent = hasFilter ? visible + ' deal' + (visible !== 1 ? 's' : '') : '';
}

search.addEventListener('input', applyFilters);
regionFilter.addEventListener('change', applyFilters);
audienceFilter.addEventListener('change', applyFilters);
filterBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    filterBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    applyFilters();
  });
});
</script>

</body>
</html>
'''


if __name__ == '__main__':
    readme_path = Path(__file__).parent.parent / 'README.md'
    out_dir = Path(__file__).parent.parent / 'docs'
    out_dir.mkdir(exist_ok=True)

    text = readme_path.read_text(encoding='utf-8')
    categories = parse_readme(text)
    html = generate_html(categories)

    (out_dir / 'index.html').write_text(html, encoding='utf-8')
    total, confirmed, expected = count_deals(categories)
    print(f"Built site: {total} deals ({confirmed} confirmed, {expected} expected) -> docs/index.html")
