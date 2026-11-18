# Live Cyber Attack Map: developer handover

This folder is everything needed to host the Live Cyber Attack Map on Datafloq's own infrastructure. A working copy currently runs at `https://edwinsallday.github.io/cyber-attack-live-map/` for reference.

## In one paragraph

It is a **static site** (HTML, CSS, JavaScript, images and one JSON data file) plus a **small Python script** that reads public cybersecurity news feeds, picks out reported attacks with keyword rules, and rewrites `data/incidents.json`. The page re-reads that file every few minutes. There is **no build step, no database, no server code, no API key and no paid service**. The script uses only the Python standard library.

## Requirements

| Part | Needs |
|---|---|
| The page | Any static web host serving over `http(s)://`. Opening `index.html` from disk does not work, because browsers block JavaScript modules on `file://` |
| The updater | Python 3.10 or newer, outbound HTTPS to the news sites and to `www.wikidata.org`, and write access to `data/`. Runs every 30 minutes; a run takes under a minute (about five minutes the very first time with an empty `data/`) |

## What's in this folder

| Path | What it is |
|---|---|
| `index.html`, `map.css`, `map.js` | The page |
| `vendor/` | three.js 0.160.0 and OrbitControls (MIT), topojson-client 3.1.0 (ISC). Served locally, no CDN |
| `assets/` | Earth at night (NASA), country borders (Natural Earth, public domain), Datafloq logo |
| `data/incidents.json` | The data the page shows. Rewritten by the updater. Its `coverage_from` field records when continuous collection began; week-on-week comparisons switch on 14 days after it, so keep this file rather than starting from an empty `data/` |
| `data/seen.json` | Stories already processed, so none is read twice. Must persist between runs |
| `pipeline/update.py` | The updater: reads feeds, classifies, merges, writes `data/` |
| `pipeline/rules.py` | Keyword rules that decide what counts as an attack and extract victim, country, type and sector |
| `pipeline/wikidata.py` | Headquarters-country lookup on Wikidata for reports that name an organisation but no country |
| `data/org_countries.json` | Cache of those lookups. Must persist between runs, like `seen.json` |
| `pipeline/countries.json` | Country positions; `pipeline/build_countries.py` rebuilds it from the border file |
| `pipeline/evaluate.py` | Accuracy check against hand-checked stories. Its test set (`eval/`) is not included because it holds feed excerpts |
| `pipeline/run_daily.ps1`, `pipeline/schedule_daily.ps1` | Windows-only helpers for running the updater on a PC. Not needed on a server |
| `.github/workflows/update.yml` | GitHub Actions job that runs the updater every 30 minutes and commits `data/` |
| `.nojekyll` | Tells GitHub Pages to serve files as they are |
| `Preview map.cmd`, `preview.ps1` | Windows-only local preview server. Not needed on a server |
| `README.md` | Fuller description: sources, how incidents are found, measured accuracy, known limits |

Note that `.github/`, `.nojekyll` and `.gitignore` start with a dot. Some upload tools (including GitHub's drag-and-drop) skip them, so push with `git`.

## Option A: GitHub Pages in the company GitHub (simplest)

1. Create a repository and push the contents of this folder (including the dot files):
   ```
   git init -b main && git add . && git commit -m "Live Cyber Attack Map"
   git remote add origin <company repo URL> && git push -u origin main
   ```
2. **Settings → Actions → General → Workflow permissions:** the workflow commits updated data back to the repository, so `GITHUB_TOKEN` needs write access. The workflow requests `contents: write`; if the organisation caps tokens at read-only, allow read and write for this repository.
3. **Settings → Pages:** Source **Deploy from a branch**, branch `main`, folder `/ (root)`.
4. **Actions → Update incidents → Run workflow** once to confirm it works (green tick, and a commit "Update incidents" if anything changed).
5. Optional: a custom domain such as `maps.datafloq.com` (Settings → Pages → Custom domain, plus a CNAME record).

GitHub disables scheduled workflows in repositories with no activity for 60 days. If the page's "Last updated" date stops moving, check the Actions tab.

## Option B: host on Datafloq's own web server

1. Upload the folder (for example by SFTP to `/wp-content/uploads/cyber-attack-map/` or to a subdomain). The WordPress Media Library usually refuses `.html` and `.js` files, so use SFTP or the host's file manager. The page works in any subfolder; all paths are relative.
2. Schedule the updater on that server, from the site folder, every 30 minutes:
   ```
   */30 * * * * cd /path/to/cyber-attack-map && python3 pipeline/update.py >> logs/update.log 2>&1
   ```
   The web server user needs write access to `data/` (and `logs/` if you keep the log).
3. Caching: cache `vendor/` and `assets/` for a long time. Keep `data/incidents.json` short (60 to 300 seconds), or the page will show stale data.
4. Delete `.github/` and the Windows helper files if you don't want them on the server. They do nothing there.

A hybrid also works: keep the code in GitHub, let the Actions workflow refresh `data/`, and deploy the repository to the web server with your usual pipeline.

## Embedding in an article

Use a **Custom HTML** block. Replace `src` with wherever you host it:

```html
<div style="position:relative;width:100%;height:min(85vh,820px);min-height:640px;border-radius:12px;overflow:hidden;">
  <iframe src="https://YOUR-HOST/cyber-attack-map/"
          title="Live Cyber Attack Map (interactive)" loading="lazy"
          style="position:absolute;inset:0;width:100%;height:100%;border:0;" allow="fullscreen"></iframe>
</div>
```

- Above 900 px wide it is a dashboard (sidebar, stat cards, globe, activity list). Below that it becomes one scrolling column.
- Plain mouse-wheel scrolling scrolls the page; Ctrl/⌘ + scroll, pinch, or the +/− buttons zoom the globe.
- `#incident=<id>` in the URL opens with that incident selected (ids are in `data/incidents.json`), and the URL updates as readers click.

## Please run only one updater

The same project currently also runs from a personal GitHub repository. Once the Datafloq copy is live, tell Edwin so he can switch his off. Two copies polling the same news sites doubles the traffic sent to them.

## The news sources, and how they are read

The list is `FEEDS` in `pipeline/update.py`: The Hacker News, BleepingComputer, Krebs on Security, Dark Reading, Infosecurity Magazine, Security Affairs, SecurityWeek, Help Net Security, The Cyber Express, Cybersecurity News, Cybersecurity Dive, Industrial Cyber, CrowdStrike Blog, CISA (two feeds), Inside Higher Ed (cyber stories only), DataBreaches.net, HIPAA Journal, The Record, SC Media, Wired Security, and the CSIS Significant Cyber Incidents timeline.

- News sources are read only through their public RSS/Atom feeds; no article pages are scraped. The one exception is the CSIS timeline, a single public web page read once per run.
- **CSIS is used for facts only.** Its material is "All Rights Reserved" and reprinting on other websites needs permission, so the page never shows CSIS's wording, only the extracted country, attack type, stated origin and month, with a link back to the timeline. If Datafloq wants to quote CSIS text, ask CSIS first (externalrelations@csis.org).
- Each site's `robots.txt` is checked first, and a site that disallows it is skipped. Hackread is excluded for that reason, and Cybernews because it blocks automated readers.
- Older feed pages (`?paged=N`, up to 4) are read only when a whole page is new and `robots.txt` allows it.
- Requests are spaced out, retried once on a slow connection, and one failing feed never stops the others. Failures appear in `feed_errors` in `data/incidents.json`.
- The requests identify themselves as `cyber-attack-map-feed-reader/1.0` (`USER_AGENT` in `pipeline/update.py`). You may want to add a Datafloq contact URL to it, which publishers appreciate.

## Things for Datafloq to decide or check

- **What gets published.** Only each story's headline, link, date and publisher name, plus fields extracted from them (victim, country, attack type). No article text, summaries or images. Whether showing third-party headlines and links on a commercial site is fine under each publisher's terms is a call for Datafloq, not something checked here.
- **The goosint-cyber-news credit.** Eight of the feeds were found through Khalil B.'s goosint-cyber-news list (CC BY-NC-SA 4.0). The list itself is not copied, only used to find public feeds, and it is credited in `README.md`. Keep that credit.
- **Credits on the page.** Under "About this map": the news sources, NASA (Earth imagery) and Natural Earth (borders). Keep them. three.js and topojson-client keep their licence headers inside `vendor/`.
- **Google Fonts.** The page loads the Outfit font from Google's servers (two lines in `index.html`). Some EU sites self-host fonts for privacy reasons. To do that, host the font files yourselves and change those lines; without them the page falls back to the system font.
- **Accuracy.** Details are extracted by keyword rules, not checked by a person. On 75 hand-checked stories the rules found 15 of 21 incident stories, got the country right for 12 of 15, and got the attack type right for 14 of 15 (figures from the first three sources only; see `README.md`). Each incident card says how solid it is and links to the original reports.
- **Wikidata lookups.** Wikidata's data is public domain (CC0), so commercial use is fine and no credit is legally required, though crediting it is good practice. Its API asks clients to identify themselves: `USER_AGENT` in `pipeline/wikidata.py` is generic, and Wikidata prefers one with a contact address, so consider adding a Datafloq contact. Lookups are cached, spaced out, capped at 30 per run, and back off when Wikidata asks.
- **The "What changed" sentence and weekly change** are computed from the reports this map collects, not from all attacks worldwide. More sources or a quiet news week shift the numbers, so treat them as a reporting trend.
- **No ransomware leak-site data is included.** A tracker such as ransomware.live would add far more activity, but its terms prohibit commercial use without written approval and forbid republishing its raw data. Not pursued.

## Changing things later

- **Add or remove a news source:** edit `FEEDS` in `pipeline/update.py`. A feed can take `"pages": 1` (no older pages), `"require": "<regex>"` (keep only matching stories) and `"default_country"`.
- **Tune what counts as an attack:** `pipeline/rules.py`. Re-run `python pipeline/evaluate.py` against a hand-checked set afterwards (you'll need to build your own `eval/` folder; the format is in the script).
- **How long incidents stay on the map:** `KEEP_DAYS` (60) in `pipeline/update.py`.
- **Colours and layout:** `map.css` (colour tokens at the top) and the attack-type colours in `TYPES` at the top of `map.js`. The interface uses Datafloq's own brand tokens from datafloq.com (`--df-brand-green` #5aaf62, `--df-brand-green-bright` #8ae64d, `--df-brand-green-hover` #4a9653, `--df-brand-ink` #0b1e16). Attack types deliberately use non-green colours so they never blend with the brand accent.

## Checklist after going live

- [ ] The page loads and the globe appears (it needs WebGL, which every current browser has).
- [ ] The sidebar's "Last updated" time is recent, and moves forward within the hour.
- [ ] `data/incidents.json` returns fresh content (not a cached copy).
- [ ] An incident card's source link opens the original article.
- [ ] The embedded version works at full width in a test post and on a phone.
- [ ] The personal copy's updater is switched off.
