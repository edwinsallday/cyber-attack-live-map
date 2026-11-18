# The Live Cyber Attack Map

An interactive 3D globe of recently reported cyber attacks and data breaches. Each pin is one incident, placed in the country where the victim is based, coloured by attack type, and linked to the news stories that reported it.

The map is a static site (HTML, CSS, JavaScript, one data file). A small Python script reads the news feeds on a schedule, picks out the incidents with keyword rules, and rewrites the data file. The page re-reads that file every five minutes. **No AI service, API key or paid service is involved.**

## Preview it on your computer

Double-click **Preview map.cmd**. A small window opens and the map appears in your browser. Close the window to stop. Double-clicking `index.html` does not work, because browsers block 3D pages opened straight from a file.

## What's in this folder

| Path | What it is |
|---|---|
| `index.html`, `map.css`, `map.js` | The map |
| `data/incidents.json` | The incidents on the map. Rewritten by the pipeline |
| `data/seen.json` | Stories already processed, so none is read twice |
| `pipeline/update.py` | Reads the feeds, merges and places incidents, writes the data |
| `pipeline/rules.py` | The keyword rules that decide what is an incident and pull out its details, including the sector |
| `pipeline/wikidata.py` | Looks up an organisation's headquarters country on Wikidata when a report names no country |
| `data/org_countries.json` | Cache of Wikidata answers, so each organisation is looked up once |
| `pipeline/evaluate.py` | Measures the rules against hand-checked stories in `eval/` |
| `pipeline/countries.json` | Country positions, built from the border file by `pipeline/build_countries.py` |
| `pipeline/run_daily.ps1`, `pipeline/schedule_daily.ps1` | The daily update on this computer, and the script that schedules it |
| `logs/` | The daily update's log. Kept out of the repository |
| `.github/workflows/update.yml` | Runs the pipeline every 30 minutes on GitHub |
| `eval/` | 75 stories with hand-checked answers. Kept out of the repository (it holds feed excerpts) |
| `vendor/`, `assets/` | three.js, Earth imagery (NASA), borders (Natural Earth), logo |

## Sources

| Source | Status |
|---|---|
| The Hacker News | Read from its RSS feed |
| BleepingComputer | Read from its RSS feed (short excerpts only, so fewer details) |
| Krebs on Security | Read from its RSS feed |
| Dark Reading, Infosecurity Magazine, Security Affairs, SecurityWeek, Help Net Security, The Cyber Express, Cybersecurity News | Read from their RSS feeds. Found through the [goosint-cyber-news](https://github.com/khalil-b1/goosint-cyber-news) list by Khalil B. (credit: goosint.com) |
| Cybersecurity Dive, Industrial Cyber, CrowdStrike Blog | Read from their RSS feeds |
| CISA | Two feeds: news, and cybersecurity advisories (mostly patch notices, so rarely an incident) |
| Inside Higher Ed | General higher-education news. Only stories mentioning a cyber incident are kept; one that names no country is placed in the United States, the publication's focus, and marked low confidence |
| DataBreaches.net, HIPAA Journal, The Record, SC Media, Wired Security | Read from their RSS feeds. HIPAA Journal covers US healthcare, so a story naming no country is placed in the United States (low confidence) |
| CSIS Significant Cyber Incidents | A web page updated monthly. Used for facts only (country, attack type, stated origin, month); its text is never shown, because CSIS material is all rights reserved. Entries show the month, not a day |
| Hackread, CSO Online, Graham Cluley, Threatpost, The Register | **Not included.** Their robots.txt does not allow automated feed readers |
| Cybersecurity Insiders, Naked Security, The Security Ledger | **Not included.** Not reachable when tested on 18 November 2026 |
| Information is Beautiful "World's Biggest Data Breaches" | **Not included.** A curated list of historical breaches, not a live feed, and its licence needs paid permission for commercial websites |
| Cybernews | **Not included.** Its feed answers automated readers with a Cloudflare challenge (HTTP 403). Add it to `FEEDS` in `pipeline/update.py` if Cybernews provides a feed URL or permission |

Only the headline, link and date of each story are published. No article text, summary or image is stored.

### How the feeds are read

- Every site's `robots.txt` is checked before its feed is read. A site that disallows it is skipped and reported in `feed_errors`.
- When a whole feed page is new (for example on the first run, or after a few days offline), up to four older pages are read as well (`?paged=2` and so on), but only where `robots.txt` allows it. SecurityWeek does not, so only its latest page is read.
- Requests are spaced out, slow connections are retried once, and one broken feed never stops the others.
- A first run with no saved data takes about five minutes; later runs take under a minute.

## Daily update on this computer

`pipeline\run_daily.ps1` runs the update once and appends what happened to `logs\update.log`. Windows Task Scheduler runs it every day at 08:00, and five minutes after you sign in to Windows, as the task **Cyber Attack Map - daily news update**.

Change the time or remove it:

```
powershell -ExecutionPolicy Bypass -File pipeline\schedule_daily.ps1 -At 06:30
powershell -ExecutionPolicy Bypass -File pipeline\schedule_daily.ps1 -Remove
```

Once the map is on GitHub, the workflow there updates the published data every 30 minutes, and this daily task only refreshes the copy on this computer.

## How an incident gets on the map

1. **Fetch.** New stories are read from each feed.
2. **Classify.** Keyword rules sort each headline into incident, vulnerability or other. Only incidents continue.
3. **Extract.** Victim (from the headline's wording), country (country names and words like "French" or "Taiwanese", ignoring ones that describe the attacker), attack type, scale, named group, and the attacker's country only when the headline itself ties the attack to one.
4. **Locate.** The pin goes at the centre of the victim's country. When a report names an organisation but no country, its headquarters country is looked up on Wikidata (public-domain data, no key; answers cached in `data/org_countries.json`). A match is accepted only when the name matches exactly and Wikidata describes it as an organisation, not a place. Incidents with no country found appear in the list but not on the globe.
5. **Sector.** Keyword rules assign an industry (healthcare, finance, education, government, retail and so on) from the headline, then the start of the excerpt. HIPAA Journal stories default to Healthcare and Inside Higher Ed stories to Education.
6. **Merge.** Stories with the same victim, or headlines sharing most of their distinctive words, become one incident with several source links. A later report can fill in a missing country, sector or attacker origin.
7. **Expire.** Incidents drop off after 60 days.

## What readers see

- **Incidents this week**, with the change against the previous 7 days and a 14-day chart.
- **Countries affected**, **most targeted sector** and **most common attack type** for the chosen time range.
- **What changed:** one or two sentences written automatically from the data, for example "41 incidents were reported in the last 7 days, up 12% on the week before. Healthcare rose from 4 to 9."
- **A breakdown under the globe** by country, sector, attack type, or per day over 30 days, with the change against the previous period. Clicking a row filters the whole page; active filters show as chips above the list.
- **Filters** by attack type (sidebar), sector and time range (map header), and free-text search.

**Comparisons wait for complete data.** News feeds only reach back a short way, so the first build under-collects older days, which would make any week-on-week change look like a surge. `data/incidents.json` therefore records `coverage_from`, the moment continuous collection began. The weekly change, the "rose from … to …" sentence and the breakdown's change column appear only once both periods fall after that date; until then the page says when they will appear, and day charts draw earlier days dimmed. Deleting `data/incidents.json` restarts this clock.

## How accurate the rules are

Measured with `python pipeline/evaluate.py` on 75 stories from 15 November 2026 that were checked by hand:

| Check | Result |
|---|---|
| Incident stories found | 15 of 21 (5 of the 6 misses were second reports of an incident another story caught) |
| Non-incidents wrongly added | 1 of 54 |
| Victim country right, on the 15 found | 12 of 15 (2 left empty, 1 guessed where the reference had none) |
| Attack type right | 14 of 15 |
| Attributed origin right | 15 of 15 |

Those 75 stories come from the first three sources only. The sources added later have not been hand-checked; a read-through of their output showed some wrong placements (for example a company pinned to the country of a supplier named in the same headline) and repeated coverage of one incident under different headlines.

The rules were adjusted while looking at these same 75 stories, so the figures are optimistic. Expect worse on new stories, and re-run the check after adding fresh hand-checked stories to `eval/`.

## Put it online (GitHub Pages)

1. Create a repository on GitHub and upload this whole folder to it.
2. **Settings → Pages**: under *Build and deployment*, choose **Deploy from a branch**, branch `main`, folder `/ (root)`.
3. **Actions → Update incidents → Run workflow** to run the first update by hand. After that it runs every 30 minutes.

To embed it in a Datafloq post, use the same iframe snippet as the data center map, pointing `src` at the Pages URL.

## Known limits

- **It is a map of reporting, not of attacks.** An incident appears when one of the sources writes about it, which can be days or weeks after it happened, and most attacks are never reported.
- **Keyword rules are blunt.** They miss incidents worded in ways they don't expect, cannot place a company unless the text names a country or the company is on a short built-in list, and cannot write a summary. Every card links to the source and says how much was found.
- **Pins are at country level.** Several incidents in one country are fanned out around its centre.
- **Arcs are rare.** They are drawn only when a report names the country behind an attack.
- **Merging is imperfect.** The same incident reported with very different headlines appears twice.
