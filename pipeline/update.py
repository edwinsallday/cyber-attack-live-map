#!/usr/bin/env python3
"""Cyber attack map: read the news feeds, pull out the incidents, write data/incidents.json.

  python pipeline/update.py                      fetch, extract with the keyword rules in rules.py, write
  python pipeline/update.py --dump pending.json  fetch only; write the stories still to be processed
  python pipeline/update.py --apply pending.json results.json
                                                 merge extraction results produced some other way (e.g. by hand)

No AI service and no API key are involved. Only headline, link and date are published. No article text is stored.
"""
import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules  # noqa: E402
import wikidata  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
INCIDENTS = DATA / "incidents.json"
SEEN = DATA / "seen.json"
ORG_CACHE = DATA / "org_countries.json"      # Wikidata answers: organisation name -> headquarters country

FEEDS = [
    {"name": "The Hacker News", "url": "https://feeds.feedburner.com/TheHackersNews"},
    {"name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/"},
    {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/"},
    # Further news sources, found through the goosint-cyber-news list (github.com/khalil-b1/goosint-cyber-news).
    {"name": "Dark Reading", "url": "https://www.darkreading.com/rss.xml"},
    {"name": "Infosecurity Magazine", "url": "https://www.infosecurity-magazine.com/rss/news/"},
    {"name": "Security Affairs", "url": "https://securityaffairs.com/feed"},
    {"name": "SecurityWeek", "url": "https://www.securityweek.com/feed/"},
    {"name": "Help Net Security", "url": "https://www.helpnetsecurity.com/feed/"},
    {"name": "The Cyber Express", "url": "https://thecyberexpress.com/feed/"},
    # Hackread (https://hackread.com/feed/) is left out: its robots.txt does not allow automated feed readers.
    {"name": "Cybersecurity News", "url": "https://cybersecuritynews.com/feed/"},
    # Added 15 November 2026.
    {"name": "Cybersecurity Dive", "url": "https://www.cybersecuritydive.com/feeds/news/"},
    {"name": "Industrial Cyber", "url": "https://industrialcyber.co/feed/"},
    {"name": "CrowdStrike Blog", "url": "https://www.crowdstrike.com/en-us/blog/feed"},
    {"name": "CISA", "url": "https://www.cisa.gov/news.xml"},
    {"name": "CISA", "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml", "pages": 1},   # mostly patch notices
    # General higher-education news: only stories that mention a cyber incident are kept, and a story that names no
    # country is placed in the United States, the publication's focus.
    {"name": "Inside Higher Ed", "url": "https://www.insidehighered.com/rss.xml",
     "require": r"cyber|hack|breach|ransomware|data (?:leak|theft|exposure)|phishing|malware|stolen data|compromis",
     "default_country": "United States", "default_sector": "Education"},
    # Added 18 November 2026: breach-focused outlets and newsrooms that allow automated feed readers.
    {"name": "DataBreaches.net", "url": "https://databreaches.net/feed/"},
    {"name": "HIPAA Journal", "url": "https://www.hipaajournal.com/feed/", "default_country": "United States",   # US healthcare
     "default_sector": "Healthcare"},
    {"name": "The Record", "url": "https://therecord.media/feed/"},
    {"name": "SC Media", "url": "https://www.scworld.com/rss"},
    {"name": "Wired Security", "url": "https://www.wired.com/feed/category/security/latest/rss", "pages": 1},
    # CSIS 'Significant Cyber Incidents' timeline (web page, updated monthly). Used for facts only (country, attack type,
    # stated origin, month); its text is never shown. Often names the country behind an attack.
    {"name": "CSIS", "url": "https://www.csis.org/programs/strategic-technologies-program/significant-cyber-incidents",
     "kind": "csis", "pages": 1},
    # Not included, because their robots.txt does not allow automated feed readers: CSO Online, Graham Cluley,
    # Threatpost, The Register. Not reachable when tested: Cybersecurity Insiders, Naked Security, The Security Ledger.
    # Cybernews (https://cybernews.com/feed/) answers automated readers with a Cloudflare challenge (HTTP 403),
    # so it is left out. Add it here if they provide a feed URL or permission.
]
USER_AGENT = "cyber-attack-map-feed-reader/1.0"
KEEP_DAYS = 60             # incidents older than this drop off the map
MERGE_DAYS = 14            # same victim reported again within this window = same incident
MAX_INPUT_CHARS = 1500     # of each story's feed excerpt kept in memory for the rules to read

TYPES = ["ransomware", "data_breach", "ddos", "phishing", "supply_chain", "espionage", "financial_theft", "other"]
TYPE_LABEL = {"ransomware": "Ransomware attack", "data_breach": "Data breach", "ddos": "DDoS attack", "phishing": "Phishing campaign",
              "supply_chain": "Supply-chain attack", "espionage": "Cyber espionage", "financial_theft": "Financial theft",
              "other": "Cyber incident"}
LARGE = {"United States of America", "Canada", "Russia", "China", "Brazil", "Australia", "India", "Indonesia",
         "Kazakhstan", "Argentina", "Greenland"}
ALIASES = {
    "united states": "United States of America", "usa": "United States of America", "us": "United States of America",
    "u.s.": "United States of America", "america": "United States of America",
    "people's republic of china": "China", "kingdom of the netherlands": "Netherlands", "kingdom of denmark": "Denmark",
    "republic of ireland": "Ireland", "state of israel": "Israel",
    "uk": "United Kingdom", "u.k.": "United Kingdom", "britain": "United Kingdom", "great britain": "United Kingdom",
    "england": "United Kingdom", "scotland": "United Kingdom", "wales": "United Kingdom",
    "uae": "United Arab Emirates", "czech republic": "Czechia", "turkiye": "Turkey", "türkiye": "Turkey",
    "the netherlands": "Netherlands", "holland": "Netherlands", "korea": "South Korea", "republic of korea": "South Korea",
    "dprk": "North Korea", "russian federation": "Russia", "prc": "China", "ivory coast": "Côte d'Ivoire",
    "bosnia and herzegovina": "Bosnia and Herz.", "dominican republic": "Dominican Rep.",
    "democratic republic of the congo": "Dem. Rep. Congo", "dr congo": "Dem. Rep. Congo",
    "central african republic": "Central African Rep.", "south sudan": "S. Sudan", "equatorial guinea": "Eq. Guinea",
    "north macedonia": "North Macedonia", "macedonia": "North Macedonia", "eswatini": "eSwatini", "burma": "Myanmar",
    "viet nam": "Vietnam", "iran, islamic republic of": "Iran", "syrian arab republic": "Syria",
}
COUNTRIES = json.loads((ROOT / "pipeline" / "countries.json").read_text(encoding="utf-8"))
COUNTRY_KEY = {k.lower(): k for k in COUNTRIES}

# ---------- feeds ----------
def strip_html(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


ATOM = "{http://www.w3.org/2005/Atom}"
MAX_PAGES = 4              # older feed pages read per source per run, where the site's robots.txt allows it
PAUSE = 1.0                # seconds between requests to the same site


def parse_date(s):
    s = (s or "").strip()
    try:
        return email.utils.parsedate_to_datetime(s).astimezone(dt.timezone.utc)      # RFC 822, the RSS standard
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%b %d, %Y %H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d"):
        try:
            d = dt.datetime.strptime(s.replace("Z", "+0000"), fmt)
            return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)
        except ValueError:
            continue
    return None


def get(url, tries=2):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=45).read()
        except urllib.error.HTTPError:
            raise                                  # a real answer from the site: do not retry
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(5)                          # slow or dropped connection: wait, then try once more


def parse_feed(raw, feed):
    """RSS or Atom -> list of stories."""
    root = ET.fromstring(raw)
    items = []
    for it in root.findall(".//item"):
        items.append((it.findtext("link"), it.findtext("title"),
                      it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or it.findtext("description"),
                      it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")))
    for it in root.findall(f".//{ATOM}entry"):
        link = next((l.get("href") for l in it.findall(f"{ATOM}link") if l.get("rel") in (None, "alternate")), None)
        items.append((link, it.findtext(f"{ATOM}title"), it.findtext(f"{ATOM}content") or it.findtext(f"{ATOM}summary"),
                      it.findtext(f"{ATOM}published") or it.findtext(f"{ATOM}updated")))
    out = []
    require = re.compile(feed["require"], re.I) if feed.get("require") else None
    for link, title, body, date in items:
        link, title, excerpt = (link or "").strip(), strip_html(title), strip_html(body)[:MAX_INPUT_CHARS]
        if not link.startswith("http") or not title:
            continue
        if require and not require.search(title + " " + excerpt):
            continue
        when = parse_date(date)
        if not when:                     # an undated story cannot be placed in time; skip it rather than guess
            continue
        story = {"source": feed["name"], "title": title, "url": link.split("?")[0],
                 "published": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "excerpt": excerpt}
        for k in ("default_country", "default_sector"):
            if feed.get(k):
                story[k] = feed[k]
        out.append(story)
    return out, len(items)


MONTHS = "January February March April May June July August September October November December".split()
CSIS_ENTRY = re.compile(r"^(" + "|".join(MONTHS) + r")\s+(\d{4}):\s*(.{20,})$", re.S)


def parse_csis(raw, feed):
    """CSIS 'Significant Cyber Incidents' is a web page of 'Month YYYY: description' paragraphs, updated monthly.
    The description is used only to extract facts; it is never published (CSIS material is all rights reserved)."""
    out = []
    # the page goes back to 2006; only entries recent enough to be shown are worth processing
    oldest = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=KEEP_DAYS + 31)
    for m in re.finditer(r"(?is)<p[^>]*>(.*?)</p>", raw.decode("utf-8", "replace")):
        para = strip_html(m.group(1))
        e = CSIS_ENTRY.match(para)
        if not e:
            continue
        when = dt.datetime(int(e.group(2)), MONTHS.index(e.group(1)) + 1, 15, 12, tzinfo=dt.timezone.utc)   # month only: mid-month
        if when < oldest:
            continue
        text = e.group(3).strip()
        key = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        out.append({"source": feed["name"], "title": text[:400], "excerpt": "", "url": f"{feed['url']}#entry-{key}",
                    "published": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "date_precision": "month", "facts_only": True})
    return out, len(out)


class Robots:
    """Reads each site's robots.txt once per run and answers whether a URL may be fetched."""
    def __init__(self):
        self.cache = {}

    def allowed(self, url):
        parts = urllib.parse.urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self.cache:
            rp = urllib.robotparser.RobotFileParser()
            try:
                rp.parse(get(base + "/robots.txt").decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as e:
                rp.parse([] if e.code in (404, 410) else ["User-agent: *", "Disallow: /"])  # missing file = no rules
            except Exception:
                rp = None                                                     # unreadable: fall back to the feed alone
            self.cache[base] = rp
        rp = self.cache[base]
        return rp.can_fetch(USER_AGENT, url) if rp else url == url.split("?")[0]


def page_url(url, n):
    return url + ("&" if "?" in url else "?") + f"paged={n}"


def fetch_all(seen, now):
    """Read every feed. When a whole page is new to us, read older pages too (WordPress-style ?paged=N),
    up to MAX_PAGES, as long as robots.txt allows it and the stories are still recent enough to show."""
    out, errors, robots = [], [], Robots()
    cutoff = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for feed in FEEDS:
        name, got, pages = feed["name"], [], 0
        try:
            if not robots.allowed(feed["url"]):
                raise RuntimeError("robots.txt does not allow this feed")
            url, limit = feed["url"], feed.get("pages", MAX_PAGES + 1)
            while True:
                try:
                    stories, raw_count = (parse_csis if feed.get("kind") == "csis" else parse_feed)(get(url), feed)
                except Exception:
                    if pages:                  # an older page that is missing or slow just ends the paging
                        break
                    raise
                pages += 1
                got += stories
                fresh = [s for s in stories if s["url"] not in seen and s["published"] >= cutoff]
                if pages >= limit or not raw_count or len(fresh) < len(stories) or not stories:
                    break
                url = page_url(feed["url"], pages + 1)
                if not robots.allowed(url):
                    break
                time.sleep(PAUSE)
            print(f"  {name}: {len(got)} stories" + (f" from {pages} pages" if pages > 1 else ""))
            out += got
        except urllib.error.HTTPError as e:
            errors.append(f"{name}: HTTP {e.code}"); print(f"  {name}: FAILED (HTTP {e.code})")
        except Exception as e:                 # one feed being down must not stop the others
            errors.append(f"{name}: {e}")
            print(f"  {name}: FAILED ({e})")
        time.sleep(PAUSE / 2)
    unique = {}
    for s in out:                              # the same story can appear in two feeds of one site
        unique.setdefault(s["url"], s)
    return list(unique.values()), errors


# ---------- location ----------
def country_key(name):
    if not name:
        return None
    k = name.strip().lower()
    k = ALIASES.get(k, k).lower() if k in ALIASES else k
    return COUNTRY_KEY.get(k)


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def locate(country, lat, lon):
    """-> (lat, lon, precision). A city position is kept only if it lies plausibly inside the stated country."""
    key = country_key(country)
    if not key:
        return None, None, "none"
    centre = COUNTRIES[key]
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and -90 <= lat <= 90 and -180 <= lon <= 180:
        if km(centre, (lat, lon)) <= (5000 if key in LARGE else 2000):
            return round(lat, 3), round(lon, 3), "city"
    return centre[0], centre[1], "country"


# ---------- merge ----------
def victim_key(name):
    k = re.sub(r"[^a-z0-9 ]", "", (name or "").lower())
    k = re.sub(r"\b(inc|ltd|llc|corp|corporation|company|co|group|plc|gmbh|sa|ag|the)\b", "", k)
    return re.sub(r"\s+", " ", k).strip()


STOP = set("that this with from into over after about their they have been were will says said more than amid your what when".split())
# Words nearly every breach headline shares; they say nothing about which incident it is.
STOP |= set("data breach breaches breached hack hacked hackers attack attacks attacker attackers cyberattack cyberattacks cyber "
            "security incident ransomware stolen steal stole users customers patients employees people million billion "
            "affecting affects affected impacts impacting exposes exposed exposing confirms confirmed reports reported "
            "reveals discloses notifies personal information leak leaked leaks systems system company firm".split())


def words(title):
    return {w for w in re.findall(r"[a-z0-9][a-z0-9'-]{3,}", title.lower()) if w not in STOP}


def alike(incident, rec):
    """Same victim country and same attack type: weaker headline overlap is then enough to call it one event."""
    key = country_key(rec.get("country"))
    return bool(key) and key == incident.get("country_key") and rec.get("attack_type") == incident.get("type")


def same_story(a, b, similar=False):
    """Two headlines from different outlets about one event share their distinctive words."""
    wa, wb = words(a), words(b)
    shared = len(wa & wb)
    if similar and shared >= 2:
        return True
    return shared >= 3 and shared / max(1, min(len(wa), len(wb))) >= 0.4


def parse(ts):
    return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def merge(incidents, items, results):
    added = merged = 0
    by_i = {r["i"]: r for r in results if isinstance(r.get("i"), int)}
    for i, it in enumerate(items):
        r = by_i.get(i)
        if not r or r["kind"] != "incident" or r.get("attack_type") not in TYPES:
            continue
        if not r.get("country") and it.get("default_country"):        # the source's home country, as a last resort
            r = {**r, "country": it["default_country"], "confidence": "low", "country_source": "source"}
        if not r.get("sector") and it.get("default_sector"):
            r = {**r, "sector": it["default_sector"]}
        r = {**r, "critical": bool(r.get("critical")) or r.get("sector") in rules.CI_SECTORS}
        title = it["title"]
        if it.get("facts_only"):          # the source's own wording is not republished; show a label built from the facts
            where = r.get("country") or "an unreported country"
            title = f"{TYPE_LABEL[r['attack_type']]} in {where} (CSIS significant cyber incidents timeline)"
        src = {"name": it["source"], "url": it["url"], "title": title, "published": it["published"]}
        if it.get("date_precision"):
            src["date_precision"] = it["date_precision"]
        vk = victim_key(r.get("victim"))
        twin = next((x for x in incidents if vk and x.get("victim_key") == vk
                     and abs((parse(x["first_seen"]) - parse(it["published"])).days) <= MERGE_DAYS), None) \
            or next((x for x in incidents if abs((parse(x["last_seen"]) - parse(it["published"])).days) <= 4
                     and any(same_story(it["title"], s["title"], alike(x, r)) for s in x["sources"])), None)
        if twin:
            if all(s["url"] != src["url"] for s in twin["sources"]):
                twin["sources"].append(src)
                twin["sources"].sort(key=lambda s: s["published"])
                twin["first_seen"] = twin["sources"][0]["published"]
                twin["last_seen"] = twin["sources"][-1]["published"]
                for f in ("records", "actor", "city", "sector"):      # a later report may add detail
                    twin[f] = twin.get(f) or r.get(f)
                twin["critical"] = bool(twin.get("critical")) or r["critical"] or twin.get("sector") in rules.CI_SECTORS
                if not twin.get("country_key") and country_key(r.get("country")):   # a later report names the country
                    t_lat, t_lon, t_prec = locate(r.get("country"), None, None)
                    twin.update(country=r["country"], country_key=country_key(r["country"]), lat=t_lat, lon=t_lon,
                                precision=t_prec, country_source=r.get("country_source"))
                a = country_key(r.get("attacker_country")) if r.get("attribution_stated") else None
                if a and not twin.get("attacker_country") and a != twin.get("country_key"):   # a later report names the origin
                    twin["attacker_country"] = r["attacker_country"]
                    twin["attacker_lat"], twin["attacker_lon"] = COUNTRIES[a]
                if twin.get("date_precision") and not it.get("date_precision"):
                    twin.pop("date_precision")                    # a dated news report replaces a month-only entry
                merged += 1
            continue
        lat, lon, precision = locate(r.get("country"), r.get("lat"), r.get("lon"))
        a_lat = a_lon = None
        a_country = r.get("attacker_country") if r.get("attribution_stated") else None
        if a_country and country_key(a_country) and country_key(a_country) != country_key(r.get("country")):
            a_lat, a_lon = COUNTRIES[country_key(a_country)]
        else:
            a_country = None
        incidents.append({
            **({"date_precision": it["date_precision"]} if it.get("date_precision") else {}),
            "id": hashlib.sha1(it["url"].encode()).hexdigest()[:10],
            "victim": r.get("victim"), "victim_key": vk, "sector": r.get("sector"),
            "country": r.get("country"), "country_key": country_key(r.get("country")), "city": r.get("city") if precision == "city" else None,
            "lat": lat, "lon": lon, "precision": precision, "country_source": r.get("country_source"),
            "type": r["attack_type"], "records": r.get("records"), "actor": r.get("actor"),
            "attacker_country": a_country, "attacker_lat": a_lat, "attacker_lon": a_lon,
            "critical": r["critical"],
            "summary": r.get("summary"), "confidence": r.get("confidence", "low"),
            "first_seen": it["published"], "last_seen": it["published"], "sources": [src],
        })
        added += 1
    return added, merged


# ---------- state ----------
def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(incidents, seen, errors, now, coverage_from):
    cutoff = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    incidents = sorted((x for x in incidents if x["last_seen"] >= cutoff), key=lambda x: x["last_seen"], reverse=True)
    DATA.mkdir(exist_ok=True)
    INCIDENTS.write_text(json.dumps({
        "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        # When continuous collection began. Feeds only reach back a little way, so counts before this date are
        # incomplete; the page compares periods (week on week) only once both fall after it.
        "coverage_from": coverage_from,
        "sources": [f["name"] for f in FEEDS],
        "feed_errors": errors,
        "incidents": incidents,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    seen_cut = (now - dt.timedelta(days=KEEP_DAYS + 30)).strftime("%Y-%m-%d")
    SEEN.write_text(json.dumps({u: d for u, d in sorted(seen.items()) if d >= seen_cut}, indent=0), encoding="utf-8")
    return len(incidents)


def place_by_wikidata(results):
    """Incidents whose report names an organisation but no country: use the organisation's headquarters country."""
    need = sorted({r["victim"] for r in results
                   if r.get("kind") == "incident" and r.get("victim") and not r.get("country")})
    if not need:
        return
    found = wikidata.countries_for(need, ORG_CACHE)
    for r in results:
        if r.get("kind") != "incident" or r.get("country") or not r.get("victim"):
            continue
        hit = found.get(r["victim"])
        if hit and country_key(hit["country"]):
            r["country"], r["country_source"] = hit["country"], "wikidata"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", metavar="PENDING")
    ap.add_argument("--apply", nargs=2, metavar=("PENDING", "RESULTS"))
    args = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    existing = load(INCIDENTS, {"incidents": []})
    incidents = existing["incidents"]
    coverage_from = existing.get("coverage_from") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    seen = load(SEEN, {})

    if args.apply:
        items = json.loads(Path(args.apply[0]).read_text(encoding="utf-8"))
        results = json.loads(Path(args.apply[1]).read_text(encoding="utf-8"))
        errors = []
    else:
        print("Reading feeds")
        fetched, errors = fetch_all(seen, now)
        items = [it for it in fetched if it["url"] not in seen]
        print(f"{len(items)} new stories")
        if args.dump:
            Path(args.dump).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
            return
        results = rules.extract(items)

    place_by_wikidata(results)
    added, merged = merge(incidents, items, results)
    done = {r["i"] for r in results if isinstance(r.get("i"), int)}
    for i, it in enumerate(items):
        if i in done:
            seen[it["url"]] = it["published"][:10]
    total = save(incidents, seen, errors, now, coverage_from)
    kinds = {}
    for r in results:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"Classified: {kinds}. New incidents: {added}, merged into existing: {merged}. On the map: {total}.")


if __name__ == "__main__":
    main()
