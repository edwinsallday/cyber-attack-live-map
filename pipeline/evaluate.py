#!/usr/bin/env python3
"""Accuracy check: run the keyword-rule extraction on saved stories and compare with reference answers.

  python pipeline/evaluate.py            uses eval/stories.json and eval/reference.json, writes eval/model.json

Does not touch data/. The eval/ folder is kept out of the repository because
stories.json holds feed excerpts, which must not be republished.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules  # noqa: E402
import update  # noqa: E402

EVAL = update.ROOT / "eval"
stories = json.loads((EVAL / "stories.json").read_text(encoding="utf-8"))
ref = {r["i"]: r for r in json.loads((EVAL / "reference.json").read_text(encoding="utf-8"))}

print(f"Extracting {len(stories)} stories with the keyword rules")
got = {r["i"]: r for r in rules.extract(stories)}
(EVAL / "model.json").write_text(json.dumps(list(got.values()), ensure_ascii=False, indent=1), encoding="utf-8")

missing = [i for i in ref if i not in got]
both = [i for i in ref if i in got]
print(f"\nReturned {len(got)} of {len(ref)} stories" + (f"; missing {missing}" if missing else ""))

# 1. incident / not incident
tp = [i for i in both if ref[i]["kind"] == "incident" and got[i]["kind"] == "incident"]
fn = [i for i in both if ref[i]["kind"] == "incident" and got[i]["kind"] != "incident"]
fp = [i for i in both if ref[i]["kind"] != "incident" and got[i]["kind"] == "incident"]
print(f"\nIncident detection: {len(tp)} agreed, {len(fn)} missed, {len(fp)} extra")
for label, ids in (("MISSED", fn), ("EXTRA", fp)):
    for i in ids:
        g = got[i]
        print(f"  {label} [{i}] {stories[i]['title'][:95]}")
        if label == "EXTRA":
            print(f"         model: {g['victim']} | {g['country']} | {g['attack_type']} | {g['confidence']}")


# 2. fields, on the incidents both agree on
def same_country(a, b):
    return update.country_key(a) == update.country_key(b)


def report(name, ok, bad):
    print(f"\n{name}: {len(ok)} of {len(ok) + len(bad)} match")
    for line in bad:
        print("  " + line)


ok, bad = [], []
for i in tp:
    (ok if same_country(ref[i]["country"], got[i]["country"]) else bad).append(
        f"[{i}] {ref[i]['victim']}: reference {ref[i]['country']}, model {got[i]['country']}")
report("Victim country", ok, bad)

ok, bad = [], []
for i in tp:
    (ok if ref[i]["attack_type"] == got[i]["attack_type"] else bad).append(
        f"[{i}] {ref[i]['victim']}: reference {ref[i]['attack_type']}, model {got[i]['attack_type']}")
report("Attack type", ok, bad)

ok, bad = [], []
for i in tp:
    r = ref[i]["attacker_country"] if ref[i]["attribution_stated"] else None
    g = got[i]["attacker_country"] if got[i]["attribution_stated"] else None
    (ok if same_country(r, g) else bad).append(f"[{i}] {ref[i]['victim']}: reference {r}, model {g}")
report("Attributed origin", ok, bad)

ok, bad = [], []
for i in tp:
    g = got[i]
    lat, lon, precision = update.locate(g["country"], g["lat"], g["lon"])
    if g["lat"] is None or precision == "city":
        ok.append(i)
    else:
        bad.append(f"[{i}] {g['victim']}: city position ({g['lat']}, {g['lon']}) rejected as outside {g['country']}")
report("City positions accepted by the sanity check", ok, bad)

print("\nVictim names (reference -> model), for judging whether merging by name will work:")
for i in tp:
    print(f"  [{i}] {ref[i]['victim']}  ->  {got[i]['victim']}")
