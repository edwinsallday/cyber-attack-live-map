"""Find the headquarters country of a named organisation on Wikidata.

Used only for incidents whose report names an organisation but no country. Wikidata's data is public domain
(CC0), needs no key, and its API asks clients to identify themselves and keep request volumes low, which this does:
answers are cached in data/org_countries.json so each name is looked up once (misses are retried after 30 days),
and a run makes at most MAX_LOOKUPS new lookups.

A result is accepted only when:
  - the name matches a Wikidata item's English label exactly, or an alias exactly (short all-caps acronyms
    such as "UTA" are not accepted as aliases, because they are too ambiguous);
  - the item's description says it is an organisation of some kind (company, university, hospital, agency ...);
  - the item has a country (P17), or a headquarters location (P159) that has one.
"""
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "cyber-attack-map/1.0 (open-source news map; python-urllib)"
MAX_LOOKUPS = 30
RETRY_MISSES_AFTER_DAYS = 30
ORG_WORDS = re.compile(
    r"\b(?:company|companies|corporation|business|enterprise|organi[sz]ation|university|college|school|hospital|health|"
    r"medical|bank|banking|insurer|insurance|agency|government|ministry|firm|retailer|retail|supermarket|chain|airline|"
    r"airport|manufacturer|maker|provider|platform|service|software|developer|exchange|group|brand|operator|publisher|"
    r"broadcaster|newspaper|subsidiary|conglomerate|startup|cooperative|council|government department|institute|"
    r"foundation|charity|laborator\w*|semiconductor|telecommunications|utility|multinational|website|video game|"
    r"department store|marketplace|carrier|postal|logistics|shipping|energy|pharmaceutical|consultancy|holding)\b", re.I)
# Descriptions of places, which share names with companies ("Coles" is also a municipality in Spain).
PLACE_WORDS = re.compile(r"\b(?:municipality|commune|village|town|city|county|province|district|region|river|mountain|island|"
                         r"department of|human settlement|ancient city|neighbo(?:u)?rhood|parish|census-designated)\b", re.I)
PAUSE = 1.2          # seconds between API calls
_last_call = [0.0]


def _api(params):
    """One polite Wikidata API call: spaced out, and waiting as told when rate-limited (HTTP 429).
    No maxlag parameter: that is meant for clients that edit Wikidata; these are read-only lookups, and with it
    Wikidata refuses every request whenever its replicas lag (seen on 18 November 2026: 24 s of lag)."""
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        wait = PAUSE - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 2:
                time.sleep(min(60, int(e.headers.get("Retry-After") or 15)))
                continue
            raise
        if data.get("error"):            # any API error means "could not check", never "not found"
            raise RuntimeError(f"Wikidata error: {data['error'].get('code')}")
        return data
    raise RuntimeError("Wikidata kept refusing requests")


def _claim_ids(entity, prop):
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and v.get("id"):
            out.append(v["id"])
    return out


def _entities(ids, props="claims|labels"):
    return _api({"action": "wbgetentities", "ids": "|".join(ids), "props": props, "languages": "en"})["entities"]


def _country_of(qid):
    ent = _entities([qid])[qid]
    countries = _claim_ids(ent, "P17")
    if not countries:                               # no country on the item itself: try its headquarters location
        hq = _claim_ids(ent, "P159")
        if hq:
            countries = _claim_ids(_entities([hq[0]])[hq[0]], "P17")
    if not countries:
        return None
    label = _entities([countries[0]], "labels")[countries[0]].get("labels", {}).get("en", {}).get("value")
    return label


def lookup(name):
    """-> {"qid", "label", "description", "country"} or None."""
    key = name.strip().lower()
    hits = _api({"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": 7}).get("search", [])
    for h in hits:
        match = h.get("match", {})
        exact_label = (h.get("label") or "").lower() == key
        exact_alias = match.get("type") == "alias" and (match.get("text") or "").lower() == key
        if not (exact_label or exact_alias):
            continue
        if exact_alias and not exact_label and name.isupper() and len(name) < 5:
            continue
        desc = h.get("description") or ""
        if not ORG_WORDS.search(desc) or PLACE_WORDS.search(desc):
            continue
        country = _country_of(h["id"])
        if country:
            return {"qid": h["id"], "label": h.get("label"), "description": h.get("description"), "country": country}
    return None


def countries_for(names, cache_path, now=None):
    """Look up each name (using and updating the cache). Returns {name: result-or-None}."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    stale = (now - dt.timedelta(days=RETRY_MISSES_AFTER_DAYS)).strftime("%Y-%m-%d")
    out, lookups = {}, 0
    for name in names:
        key = name.strip().lower()
        hit = cache.get(key)
        if hit is not None and (hit.get("country") or hit.get("checked", "") >= stale):
            out[name] = hit if hit.get("country") else None
            continue
        if lookups >= MAX_LOOKUPS:
            out[name] = None
            continue
        lookups += 1
        try:
            res = lookup(name)
        except Exception as e:                       # Wikidata unavailable: leave the incident unplaced this run
            print(f"  Wikidata lookup failed for {name!r}: {e}")
            out[name] = None
            continue
        cache[key] = {**(res or {}), "checked": now.strftime("%Y-%m-%d")}
        out[name] = res
    cache_path.parent.mkdir(exist_ok=True)
    cache_path.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    if lookups:
        print(f"  Wikidata: {lookups} new lookups, {sum(1 for v in out.values() if v)} of {len(out)} names placed")
    return out
