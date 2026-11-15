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
| `pipeline/rules.py` | The keyword rules that decide what is an incident and pull out its details |
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
| Hackread | **Not included.** Its robots.txt does not allow automated feed readers |
| Cybernews | **Not included.** Its feed answers automated readers with a Cloudflare challenge (HTTP 403). Add it to `FEEDS` in `pipeline/update.py` if Cybernews provides a feed URL or permission |

Only the headline, link and date of each story are published. No article text, summary or image is stored.

### How the feeds are read

- Every site's `robots.txt` is checked before its feed is read. A site that disallows it is skipped and reported in `feed_errors`.
- When a whole feed page is new (for example on the first run, or after a few days offline), up to four older pages are read as well (`?paged=2` and so on), but only where `robots.txt` allows it. SecurityWeek does not, so only its latest page is read.
- Requests are spaced out, slow connections are retried once, and one broken feed never stops the others.
- A first run with no saved data takes about five minutes; later runs take under a minute.

## Daily update on this computer

`pipeline\run_daily.ps1` runs the update once and appends what happened to `logs\update.log`. Windows Task Scheduler runs it every day at 08:00 as the task **Cyber Attack Map - daily news update**. If the computer is off or asleep at 08:00, it runs as soon as it is back on and online.

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
4. **Locate.** The pin goes at the centre of the victim's country. Incidents with no country found appear in the list but not on the globe.
5. **Merge.** Stories with the same victim, or headlines sharing most of their distinctive words, become one incident with several source links.
6. **Expire.** Incidents drop off after 60 days.

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
