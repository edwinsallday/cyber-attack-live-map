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
    "ConnectWise": "United States", "N-able": "United States", "CrowdStrike": "United States",
    # banks, payment companies and digital wallets
    "Crédit Mutuel": "France", "Credit Mutuel": "France", "Crédit Agricole": "France", "BNP Paribas": "France",
    "Société Générale": "France", "HSBC": "United Kingdom", "Barclays": "United Kingdom", "Lloyds": "United Kingdom",
    "NatWest": "United Kingdom", "Santander": "Spain", "BBVA": "Spain", "Deutsche Bank": "Germany", "Commerzbank": "Germany",
    "ING": "Netherlands", "ABN AMRO": "Netherlands", "Rabobank": "Netherlands", "UBS": "Switzerland", "UniCredit": "Italy",
    "JPMorgan": "United States", "Chase": "United States", "Wells Fargo": "United States", "Bank of America": "United States",
    "Citibank": "United States", "Citigroup": "United States", "Capital One": "United States", "Goldman Sachs": "United States",
    "Commonwealth Bank": "Australia", "Westpac": "Australia", "ANZ": "Australia", "RBC": "Canada", "TD Bank": "Canada",
    "DBS": "Singapore", "PayPal": "United States", "Venmo": "United States", "Cash App": "United States", "Zelle": "United States",
    "Stripe": "United States", "Revolut": "United Kingdom", "Monzo": "United Kingdom", "Klarna": "Sweden", "Adyen": "Netherlands",
    "GCash": "Philippines", "PayMaya": "Philippines", "M-Pesa": "Kenya", "Safaricom": "Kenya", "Paytm": "India",
    "Alipay": "China", "Nubank": "Brazil", "Mercado Pago": "Argentina", "Airbus": "France", "Orange": "France", "Ubisoft": "France",
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
INCIDENT = re.compile(r"\b(?:breach(?:es|ed)?|hacked|stole|stolen|theft|heist|ransomware attack|cyber ?attacks?|extort\w*|leak(?:ed|s)?|hijacked|hijacks|compromised?|sabotage|intercept\w*|implants?|spy on|wip(?:e|ed|er)|defaced|knocked offline|infect\w*|attacks target"
                      r"|cyber ?incident|security incident|cybersecurity incident|unauthori[sz]ed (?:access|trades|transactions))\b", re.I)
# Trend pieces, research and commentary that mention attacks without reporting one.
NOT_AN_EVENT = re.compile(r"\b(?:increasingly|shed light|fail to|extends|propaganda|court|clears|trend|lessons|inside|explained|"
                          r"what we know|analysis|opinion)\b|\bmost\b.*\bvictims\b|^\w+:\s*AI\b", re.I)

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
NOT_A_VICTIM = re.compile(r"^(?:January|February|March|April|May|June|July|August|September|October|November|December|"
                          r"Announced|Suspected|Reported|Alleged|Hackers?|Attackers?|Researchers?|Experts?|Police|New|Critical|Massive|Over|Three|Two|Russian|Chinese|Iranian|North Korean|CISA|Feds|Tech Firms|Threat Actors?)\b|" + "|".join(re.escape(k) + r"$" for k in ("France", "Germany", "U.S.", "US", "U.K.", "UK", "China", "Russia", "Iran")))
VICTIM_PATTERNS = [
    re.compile(r"^(" + NAME + r") (?:[Cc]onfirms|[Dd]iscloses|[Aa]dmits|[Ss]uffers|[Hh]it [Bb]y|[Bb]reached|[Hh]acked|[Nn]otifies|[Ii]nvestigat\w+)\b"),
    re.compile(r"^(" + NAME + r") [Ss]ays (?=.*\b(?:[Ss]tolen|[Bb]reach|[Hh]acked|[Aa]ttack|[Ll]eak))"),
    re.compile(r"\b(?:[Bb]reaches|[Hh]acks|[Ee]xtorted|[Ee]xtorts|[Hh]its|[Ss]tole (?:[Ff]rom|[Dd]ata [Ff]rom)|[Dd]ata [Ff]rom(?: the)?) (" + NAME + r")"),
    re.compile(r"\b(?:[Aa]ttack|[Bb]reach|[Hh]ack|[Cc]yberattack|[Ii]ntrusion) (?:[Oo]n|[Aa]t|[Aa]gainst|[Oo]f) (" + NAME + r")"),
    re.compile(r"^(" + NAME + r") (?:[Dd]ata )?(?:[Bb]reach|[Cc]yberattack|[Hh]ack)\b"),
    re.compile(r"(" + NAME + r")['’]s (?:[Dd]ata )?(?:[Bb]reach|[Hh]ack|[Cc]yberattack|[Ll]eak)\b"),
    re.compile(r"^(" + NAME + r") (?:has |have )?(?:reportedly )?(?:leaked|exposed|suffered|been hit|been hacked|been breached)\b"),
]
TRAILING = re.compile(r"\s+(?:Prior|After|Amid|Over|Via|And|In|To|For|With|Using|Customers?)$")
# Verbs that end a company name ("Karaoke Giant Reveals Data ..." -> "Karaoke Giant")
NAME_STOP = re.compile(r"\s+(?:Reveals?|Confirms?|Discloses?|Investigat\w+|Notifies|Says|Reports?|Suffers?|Hit|Affects?|Affecting|"
                       r"Impacts?|Impacting|Exposes?|Compromises?|Leaks?|Puts|Hits?|Data|Breach\w*|Restarts?|Warns?)\b.*$")
# Descriptions in front of a name ("Market Research Giant Ipsos" -> "Ipsos")
DESCRIPTOR = re.compile(r"^(?:[A-Z][\w-]*\s+){0,3}(?:Giant|Firm|Maker|Provider|Operator|Retailer|Chain|Startup|Insurer|Airline|"
                        r"Lender|Platform|Company|Subsidiary)\s+(?=[A-Z])")


def victim_of(title):
    for pat in VICTIM_PATTERNS:
        m = pat.search(title)
        if m:
            v = NAME_STOP.sub("", m.group(1))
            v = re.sub(r"['’]s$", "", TRAILING.sub("", v)).strip(" ,.'’")
            stripped = DESCRIPTOR.sub("", v)
            v = stripped if len(stripped) > 1 else v
            if GENERIC_NAME.search(v):         # "Karaoke Giant": a description, not a name
                return None
            if len(v) > 1 and not NOT_A_VICTIM.search(v):
                return v
    return None


GENERIC_NAME = re.compile(r"(?:^|\s)(?:Giant|Firm|Maker|Provider|Operator|Retailer|Chain|Startup|Company|Companies|Firms)$")


# ---------- sector ----------
# Checked in order; the first match wins. Matched against the headline first, then the start of the excerpt.
SECTOR_RULES = [
    ("Crypto & digital assets", r"crypto|bitcoin|ethereum|blockchain|\bdefi\b|binance|coinbase|kraken|bybit|bitget|trezor|ledger wallet|"
                                r"\bnft\b|stablecoin|\bwallets?\b.*\b(?:seed|recovery|private key)"),
    # "health" alone also describes data ("student health and financial data"), so it counts only when no
    # data word follows closely.
    ("Healthcare", r"hospital|clinic|medical|patients?\b|pharma|dental|hipaa|\bnhs\b|biotech|oncology|epilep|physician|ambulance|"
                   r"surger|care home|nursing home|laborator|health ?care|health (?:system|service|services|network|group|centre|"
                   r"center|authority|board|plan|insurer|trust)|\bhealth\b(?![\w ,&-]{0,25}\b(?:data|information|records|details)\b)"),
    ("Education", r"universit|college|school|student|education|academ|campus|k-12|alumni"),
    ("Banking & finance", r"\bbanks?\b|banking|credit union|financial (?:services|institution|firm|group|company|regulator|sector)|"
                          r"fintech|insur(?:er|ance)|lender|mortgage|investment firm|asset manag|securities|brokerage|stock exchange|"
                          r"pension|\bloans?\b|trading account|stockal|cr[ée]dit (?:mutuel|agricole|suisse)|\bswift\b|\batms?\b|"
                          r"payment (?:app|provider|processor|platform|company|service|network)|card (?:issuer|processor)|"
                          r"digital wallet|e-?wallet|mobile money|money transfer|remittance|paypal|venmo|cash app|zelle|revolut|"
                          r"\bwise\b|klarna|stripe|\bsquare\b|gcash|\bmaya\b|paymaya|m-pesa|paytm|alipay|wechat pay|apple pay|"
                          r"google pay|\bvisa\b|mastercard|american express|\bamex\b"),
    ("Telecoms", r"telecom|telco|mobile operator|mobile network|carrier|broadband|\bisp\b|\bsms\b"),
    ("Energy & utilities", r"\benergy\b|\boil\b|\bgas\b(?! station)|power (?:grid|plant|station|company|utility|supplier|provider|"
                           r"outage|network|distribution)|electricity|electric (?:utility|company|cooperative|grid)|\butilit(?:y|ies)\b|"
                           r"water (?:utility|supply|treatment|system|plant|authority|company|district)|wastewater|nuclear|"
                           r"pipeline operator|solar|wind farm|substation|\bgrid\b|engie"),
    ("Transport & logistics", r"airline|airport|aviation|\brail|railway|shipping|maritime|\bport of|logistics|transport|freight|"
                              r"maersk|transit|metro\b|passenger|widerøe|tunnel|postal|la poste|maileva|post office|courier"),
    ("Travel & hospitality", r"hotel|resort|restaurant|travel|cruise|theme park|legoland|expedia|booking|karaoke|casino"),
    ("Retail & e-commerce", r"retail|\bstores?\b|\bshops?\b|e-?commerce|supermarket|grocer|fashion|asos|coles|woolworths|sogo|muji|"
                            r"gift card|card skimm|checkout|consumer"),
    ("Manufacturing & industry", r"manufactur|factory|industrial|\bics\b|\bot\b|scada|\bplc\b|automotive|carmaker|chemical|steel|"
                                 r"refrigeration|semiconductor|tsmc|chip ?maker|drone"),
    ("Media & entertainment", r"\bmedia\b|news(?:paper)?s?\b|broadcast|gaming|video game|\bgames?\b|entertainment|streaming|"
                              r"publisher|capcom|sega|\bcnn\b|\bbbc\b|fox news"),
    ("Legal & professional services", r"law firm|legal|accounting|consult|audit|market research|ipsos|recruit"),
    ("Charities & non-profits", r"charit|non-?profit|\bngo\b|children['’]s aid|foundation"),
    ("Government & defence", r"government|ministry|\bagency\b|council|municipal|city hall|county|federal|police|military|"
                             r"defen[cs]e|army|navy|parliament|embassy|public sector|\bfbi\b|\bnato\b|state department|"
                             r"department of|town\b|\bcity of\b"),
    ("Technology", r"software|saas|cloud|\btech\b|developer|github|\bai\b|platform|\bapp\b|open[- ]source|\bnpm\b|pypi|"
                   r"it services|\bmsps?\b|data cent|screenconnect|optimizely|docker|website|vpn|microsoft|apple|google|"
                   r"teams|exchange servers?|infoblox|gyazo"),
]
SECTOR_RES = [(name, re.compile(pat, re.I)) for name, pat in SECTOR_RULES]

# "Critical infrastructure": the essential-services sectors, plus stories about industrial control systems,
# operational technology or critical infrastructure in general.
CI_SECTORS = {"Energy & utilities", "Healthcare", "Banking & finance", "Telecoms", "Transport & logistics"}
CI_WORDS = re.compile(r"critical infrastructure|critical national infrastructure|\bics\b|\bscada\b|\bplcs?\b|industrial control|"
                      r"operational technology|\bot (?:network|system|environment|device|controller)s?|refrigeration|"
                      r"cold chain|food supply|water (?:utility|supply|treatment|system)|power grid|electricity|dam\b|"
                      r"emergency services|911\b", re.I)


def is_critical(sector, text):
    return sector in CI_SECTORS or bool(CI_WORDS.search(text or ""))


def sector_of(title, excerpt):
    for text in (title, (excerpt or "")[:300]):
        for name, rx in SECTOR_RES:
            if rx.search(text):
                return name
    return None


def classify(title, excerpt):
    if NOT_NEWS.search(title) or NOT_AN_EVENT.search(title):
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
            victim=victim, country=country, sector=sector_of(title, excerpt),
            critical=is_critical(sector_of(title, excerpt), title + " " + excerpt[:300]),
            attack_type=next((t for t, pat in TYPE_RULES if re.search(pat, low)), "other"),
            records=m_scale.group(1).strip() if m_scale else None,
            actor=m_actor.group(1) if m_actor else None,
            attacker_country=attackers[0] if attackers else None, attribution_stated=bool(attackers),
            confidence="medium" if victim and country else "low",
        )
        out.append(rec)
    return out
