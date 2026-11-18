"""Keyword-rule extraction: turns a news item into the same record the map uses, with no AI and no API key.

It reads the headline first and the feed excerpt second. It is deliberately cautious: it never writes a summary
(that would mean copying the source's words), never marks anything "high" confidence, and leaves a field empty
rather than guess. Expect it to miss incidents and to leave many without a location.
"""
import json
import re
from pathlib import Path

COUNTRIES = json.loads((Path(__file__).resolve().parent / "countries.json").read_text(encoding="utf-8"))

# ---------- places ----------
# Names that are also common words, people or US states are left out.
SKIP = {"Georgia", "Chad", "Jordan", "Niger", "Turkey", "Guinea", "Mali", "Jersey", "Guam", "Togo", "Oman", "Cuba"}
PLACE = {k: k for k in COUNTRIES if "." not in k and k not in SKIP and len(k) > 3}
PLACE.update({
    "United States": "United States", "U.S.": "United States", "US": "United States", "USA": "United States", "American": "United States",
    "United Kingdom": "United Kingdom", "U.K.": "United Kingdom", "UK": "United Kingdom", "British": "United Kingdom", "Britain": "United Kingdom",
    "French": "France", "German": "Germany", "Israeli": "Israel", "Taiwanese": "Taiwan", "Japanese": "Japan", "Chinese": "China",
    "China-Nexus": "China", "Russian": "Russia", "Iranian": "Iran", "North Korean": "North Korea", "DPRK": "North Korea",
    "South Korean": "South Korea", "Indian": "India", "Australian": "Australia", "Canadian": "Canada", "Dutch": "Netherlands",
    "Spanish": "Spain", "Italian": "Italy", "Ukrainian": "Ukraine", "Polish": "Poland", "Swedish": "Sweden", "Brazilian": "Brazil",
    "Mexican": "Mexico", "Turkish": "Turkey", "Türkiye": "Turkey", "Saudi": "Saudi Arabia", "UAE": "United Arab Emirates",
    "Emirati": "United Arab Emirates", "Singaporean": "Singapore", "Indonesian": "Indonesia", "Vietnamese": "Vietnam",
    "Philippine": "Philippines", "Filipino": "Philippines", "Malaysian": "Malaysia", "Pakistani": "Pakistan", "Swiss": "Switzerland",
    "Belgian": "Belgium", "Irish": "Ireland", "Danish": "Denmark", "Norwegian": "Norway", "Finnish": "Finland", "Czech": "Czechia",
    "Austrian": "Austria", "Portuguese": "Portugal", "Greek": "Greece", "Egyptian": "Egypt", "South African": "South Africa",
    "Nigerian": "Nigeria", "Kenyan": "Kenya", "Argentine": "Argentina", "Colombian": "Colombia", "Chilean": "Chile",
    "Korean": "South Korea", "Thai": "Thailand", "Hong Kong": "Hong Kong", "Singapore": "Singapore",
})
US_STATE_PREFIX = re.compile(r"^(?:AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY):\s")
# Country prefixes DataBreaches.net uses. Codes that are also US state codes (DE, IN, ...) are deliberately absent.
COUNTRY_PREFIXES = {"Ca": "Canada", "CA:": None, "SG": "Singapore", "JPN": "Japan", "JP": "Japan", "UK": "United Kingdom",
                    "AU": "Australia", "NZ": "New Zealand", "HK": "Hong Kong", "KR": "South Korea", "PH": "Philippines",
                    "MY": "Malaysia", "TW": "Taiwan", "FR": "France", "NL": "Netherlands", "IE": "Ireland", "IT": "Italy",
                    "ES": "Spain", "BR": "Brazil", "MX": "Mexico", "ZA": "South Africa", "IL": None, "TH": "Thailand",
                    "VN": "Vietnam", "ID": None, "CN": "China", "TR": "Turkey", "SE": "Sweden", "NO": "Norway", "DK": "Denmark",
                    "FI": "Finland", "BE": "Belgium", "CH": "Switzerland", "AT": "Austria", "PL": "Poland", "PT": "Portugal"}
COUNTRY_PREFIXES = {k: v for k, v in COUNTRY_PREFIXES.items() if v}
COUNTRY_PREFIX = re.compile(r"^(" + "|".join(sorted(COUNTRY_PREFIXES, key=len, reverse=True)) + r"):\s")
# US states (Georgia is left out: it is also a country). Their names place a story in the United States.
PLACE.update({s: "United States" for s in (
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida", "Hawaii",
    "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts",
    "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
    "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
    "West Virginia", "Wisconsin", "Wyoming")})
PLACE_RE = re.compile(r"(?<![\w-])(" + "|".join(sorted((re.escape(k) for k in PLACE), key=len, reverse=True)) + r")(?![\w])")

# Where a few very well-known organisations are based (used only when the text names no country).
HQ = {
    "Microsoft": "United States", "Google": "United States", "Apple": "United States", "Amazon": "United States", "Meta": "United States",
    "GitHub": "United States", "FBI": "United States", "Cisco": "United States", "Oracle": "United States", "Boeing": "United States",
    "Cursor": "United States", "OpenAI": "United States", "Anthropic": "United States", "Salesforce": "United States",
    "Cloudflare": "United States", "Okta": "United States", "Snowflake": "United States", "AT&T": "United States", "Verizon": "United States",
    "T-Mobile": "United States", "Coinbase": "United States", "Samsung": "South Korea", "Sony": "Japan", "Toyota": "Japan",
    "Nissan": "Japan", "Huawei": "China", "Alibaba": "China", "SAP": "Germany", "Siemens": "Germany", "Volkswagen": "Germany",
    "Trezor": "Czechia", "Nokia": "Finland", "Ericsson": "Sweden", "Vodafone": "United Kingdom", "NHS": "United Kingdom",
    "Marks & Spencer": "United Kingdom", "Jaguar Land Rover": "United Kingdom", "Check Point": "Israel", "Qantas": "Australia",
    "Optus": "Australia", "Medibank": "Australia", "Maersk": "Denmark", "Expedia": "United States", "Uber": "United States",
    "ConnectWise": "United States", "N-able": "United States", "CrowdStrike": "United States", "Airbus": "France", "Orange": "France", "Ubisoft": "France",
}

ATTACKER_AFTER = re.compile(r"^[\s-]*(?:-?(?:linked|nexus|aligned|backed|based|sponsored)\b|(?:state-sponsored |nation-state )?(?:hackers?|threat actors?|state actors?|spies|apt\b|cyber unit|campaign|group)|\(?aka\b|['’]s (?:islamic|irgc|gru|mss|lazarus|apt|\$?\d|\w+ (?:hackers?|group|scheme|spies)))", re.I)
ATTACKER_BEFORE = re.compile(r"(?:blam\w+|attribut\w+ (?:[^.]{0,40} )?to|pins? [^.]{0,60} on|tied to|linked to|backed by|on behalf of|unit of|carried out by)\s+(?:the\s+)?$", re.I)
REPORTER_AFTER = re.compile(r"^(?:['’]s)?\s*(?:sanctions?|disrupts?|arrests?|charges|indicts|seizes|cybersecurity and infrastructure|federal|government|department|treasury|justice|police|authorities)", re.I)
TARGET_BEFORE = re.compile(r"(?:target(?:ed|ing|s)?|against|across|mostly in|based in|users in|organi[sz]ations in|sites in|attack on|attacks on)\s+(?:the\s+)?(?:\w+\s+){0,2}$", re.I)
TARGET_AFTER = re.compile(r"^\s*(?:organi[sz]ations?|compan(?:y|ies)|firms?|retail\w*|government|military|defen[cs]e|users|agenc(?:y|ies)|banks?|hospitals?|telecom\w*|universit\w+|police|ministry|airline|airport|sites|energy|water|health\w*)", re.I)


def places(text):
    """-> (victim_countries, attacker_countries) in order of appearance."""
    victims, attackers = [], []
    for m in PLACE_RE.finditer(text):
        country, before, after = PLACE[m.group(1)], text[max(0, m.start() - 60):m.start()], text[m.end():m.end() + 45]
        if ATTACKER_AFTER.match(after) or ATTACKER_BEFORE.search(before):
            attackers.append(country)
        elif REPORTER_AFTER.match(after):
            continue
        else:
            victims.append((country, bool(TARGET_BEFORE.search(before) or TARGET_AFTER.match(after))))
    return victims, attackers


# ---------- what kind of story ----------
NOT_NEWS = re.compile(r"^(?:webinar|threatsday|weekly recap|weekly update|in other news|week in review|how |why |when |what |who |want |"
                      r"beyond |we built|best |top \d)|\?\s*$|: the case for|\broundup\b|\bguide to\b|\bstatistics\b|\btools in \d{4}\b", re.I)
POLICE = re.compile(r"\b(?:arrests?|arrested|takes? down|took down|seizes?|seized|sanctions?|dismantle[sd]?|disrupts|suspects?|indict\w*|sentenced|pleads?|extradit\w+|crackdown|disrupted after"
                    r"|pushes|funding|reprimands?|fines?|fined|lawsuit|sues|sued|settles?|settlement|regulators?|legislation"
                    r"|cracks? down|cracked down|task force|liability|urges?|guidance|survey|study finds|report finds|recovers"
                    r"|acquits?|acquitted|convicted|jailed|prison|sue|study|warned|warns of|insights)\b"
                    r"|\bbreach report\b", re.I)
VULN = re.compile(r"\b(?:flaws?|patch(?:es|ed)?|cve-\d|vulnerabilit\w+|zero-day|bugs?|fix(?:es|ed)?|poc|exploits? work|security updates?|rce)\b", re.I)
HYPOTHETICAL = re.compile(r"\b(?:could|can|lets?|may|might|would|warns of|show|shows|benchmark)\b", re.I)
CONFIRMED = re.compile(r"\b(?:confirms?|confirmed|discloses?|disclosed|admits?|blames?|says stolen|suffers?|suffered|hit by|disrupted by|breached|hacked|extorted|stole)\b", re.I)
INCIDENT = re.compile(r"\b(?:breach(?:es|ed)?|hacked|stole|stolen|theft|heist|ransomware attack|cyber ?attacks?|extort\w*|leak(?:ed|s)?|hijacked|hijacks|compromised?|sabotage|intercept\w*|implants?|spy on|wip(?:e|ed|er)|defaced|knocked offline|infect\w*|attacks target)\b", re.I)

TYPE_RULES = [
    ("ransomware", r"ransomware|extort"),
    ("ddos", r"\bddos\b|denial[- ]of[- ]service|knocked offline"),
    ("financial_theft", r"crypto(?:currency)? (?:theft|heist)|stole (?:over |more than |about )?\$|\$[\d.,]+ ?(?:million|billion)? in crypto|heist|drained"),
    ("espionage", r"espionage|spy(?:ing)? |spies|state-sponsored|nation-state|intercept"),
    ("supply_chain", r"supply[- ]chain|npm|pypi|malicious (?:package|extension|update)|extension|marketplace|repositor(?:y|ies)|implants? in|github accounts|msps?\b|rogue clients"),
    ("phishing", r"phishing|deepfake|social engineering|vishing|smishing"),
    ("data_breach", r"breach|leak|stolen|stole|exposed|unauthorized access|data theft"),
]
ACTORS = re.compile(r"\b(ShinyHunters|Qilin|LockBit|Lazarus(?: Group)?|Turla|Scattered Spider|Akira|Clop|Cl0p|Play ransomware|RansomHub|Salt Typhoon|Volt Typhoon|Sandworm|Blind Eagle|Black Basta|Medusa|Rhysida|BlackCat|ALPHV|Kimsuky|Fancy Bear|Cozy Bear|APT\d{1,2}|UNC\d{3,5}|IRGC)\b")
SCALE = re.compile(r"((?:about |over |more than |nearly |at least |an estimated )?(?:\$\s?[\d.,]+\s?(?:million|billion|[MBK])?|[\d.,]+\+?\s?(?:million|billion|[MK])?\s(?:customers|users|records|accounts|people|patients|employees|endpoints|organi[sz]ations|sites|repositories|servers|devices|wallets|agents)))", re.I)

NAME = r"[A-Z][\w.&'’-]*(?: (?:[A-Z&][\w.&'’-]*|AI|of|de))*"
NOT_A_VICTIM = re.compile(r"^(?:Hackers?|Attackers?|Researchers?|Police|New|Critical|Massive|Over|Three|Two|Russian|Chinese|Iranian|North Korean|CISA|Feds|Tech Firms|Threat Actors?)\b|" + "|".join(re.escape(k) + r"$" for k in ("France", "Germany", "U.S.", "US", "U.K.", "UK", "China", "Russia", "Iran")))
VICTIM_PATTERNS = [
    re.compile(r"^(" + NAME + r") (?:[Cc]onfirms|[Dd]iscloses|[Aa]dmits|[Ss]uffers|[Hh]it [Bb]y|[Bb]reached|[Hh]acked|[Nn]otifies|[Ii]nvestigat\w+)\b"),
    re.compile(r"^(" + NAME + r") [Ss]ays (?=.*\b(?:[Ss]tolen|[Bb]reach|[Hh]acked|[Aa]ttack|[Ll]eak))"),
    re.compile(r"\b(?:[Bb]reaches|[Hh]acks|[Ee]xtorted|[Ee]xtorts|[Hh]its|[Ss]tole (?:[Ff]rom|[Dd]ata [Ff]rom)|[Dd]ata [Ff]rom(?: the)?) (" + NAME + r")"),
    re.compile(r"\b(?:[Aa]ttack|[Bb]reach|[Hh]ack|[Cc]yberattack|[Ii]ntrusion) (?:[Oo]n|[Aa]t|[Aa]gainst|[Oo]f) (" + NAME + r")"),
    re.compile(r"^(" + NAME + r") (?:[Dd]ata )?(?:[Bb]reach|[Cc]yberattack|[Hh]ack)\b"),
]
TRAILING = re.compile(r"\s+(?:Prior|After|Amid|Over|Via|And|In|To|For|With|Using|Customers?)$")


def victim_of(title):
    for pat in VICTIM_PATTERNS:
        m = pat.search(title)
        if m:
            v = TRAILING.sub("", m.group(1)).strip(" ,.'’")
            if len(v) > 1 and not NOT_A_VICTIM.search(v):
                return v
    return None


def classify(title, excerpt):
    if NOT_NEWS.search(title):
        return "other"
    confirmed = bool(CONFIRMED.search(title))
    if POLICE.search(title) and not confirmed:
        return "other"
    if INCIDENT.search(title) or confirmed and INCIDENT.search(excerpt[:300]):
        if HYPOTHETICAL.search(title) and not confirmed:
            return "vulnerability" if VULN.search(title) else "other"
        if VULN.search(title) and not confirmed and not victim_of(title):
            return "vulnerability"
        return "incident"
    return "vulnerability" if VULN.search(title) else "other"


def extract(items):
    out = []
    for i, it in enumerate(items):
        title, excerpt = it["title"], it.get("excerpt") or ""
        kind = classify(title, excerpt)
        rec = dict(i=i, kind=kind, victim=None, sector=None, country=None, city=None, lat=None, lon=None, attack_type=None,
                   records=None, actor=None, attacker_country=None, attribution_stated=False, summary=None, confidence="low")
        if kind != "incident":
            out.append(rec)
            continue
        text = title + ". " + excerpt[:600]
        victim = victim_of(title)
        t_victims, t_attackers = places(title)
        e_victims, e_attackers = places(excerpt[:600])
        m_state = US_STATE_PREFIX.match(title)                     # "MA: Andover ..." style headlines (DataBreaches.net)
        m_cc = COUNTRY_PREFIX.match(title)                         # "SG: ...", "Ca: ...", "JPN: ..."
        country = ("United States" if m_state else None) \
            or (COUNTRY_PREFIXES[m_cc.group(1)] if m_cc else None) \
            or (t_victims[0][0] if t_victims else None) \
            or next((c for c, targeted in e_victims if targeted), None) \
            or next((c for org, c in HQ.items() if re.search(r"\b" + re.escape(org) + r"\b(?!:| (?:[Ss]ays|[Ww]arns|[Aa]rrests|[Aa]ttributes|[Rr]esearchers))", victim or title)), None)
        # Attribution is the most sensitive claim on the map, so it is taken from the headline only.
        attackers = [a for a in t_attackers if a != country]
        low = text.lower()
        m_scale, m_actor = SCALE.search(title), ACTORS.search(text)      # scale from the headline only: excerpts are too noisy
        rec.update(
            victim=victim, country=country,
            attack_type=next((t for t, pat in TYPE_RULES if re.search(pat, low)), "other"),
            records=m_scale.group(1).strip() if m_scale else None,
            actor=m_actor.group(1) if m_actor else None,
            attacker_country=attackers[0] if attackers else None, attribution_stated=bool(attackers),
            confidence="medium" if victim and country else "low",
        )
        out.append(rec)
    return out
