#!/usr/bin/env python3
"""Validate the merged offline question banks in anre_trainer.html (stdlib only)."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app" / "src" / "main" / "assets" / "anre_trainer.html"

REQUIRED = ("Intrebare", "A", "B", "C", "Explicatie", "Sursa", "Baza_verificare")
EXPECTED_BANKS = {
    "ANRE oficial": 822,
    "Grad II · Chestionare ANRE": 541,
    "Grad II · Scientia": 577,
    "Grad II · Old": 635,
}
EXPECTED_OFFICIAL_CATEGORIES = {
    "Electrotehnică": 595,
    "Norme tehnice": 115,
    "Legislație": 112,
}


def load_data():
    html = HTML.read_text(encoding="utf-8")
    marker = "const DATA="
    start = html.find(marker)
    assert start >= 0, "const DATA= not found"
    data, _ = json.JSONDecoder().raw_decode(html[start + len(marker):])
    assert isinstance(data, list), "DATA is not a list"
    return data


def main():
    data = load_data()

    assert len(data) == 2575, "total is %d, expected 2575" % len(data)
    ids = [q.get("ID") for q in data]
    assert len(set(ids)) == len(ids), "duplicate IDs found"
    print("Total: %d" % len(data))
    print("Unique IDs: %d" % len(set(ids)))

    banks = Counter(q.get("Banca") for q in data)
    for bank, expected in EXPECTED_BANKS.items():
        assert banks.get(bank) == expected, (
            "bank %r has %d questions, expected %d" % (bank, banks.get(bank, 0), expected))
    print("Banca: " + ", ".join("%s=%d" % (b, banks[b]) for b in EXPECTED_BANKS))

    for q in data:
        qid = q.get("ID")
        for field in REQUIRED:
            value = q.get(field)
            assert str("" if value is None else value).strip(), (
                "%s has empty %s" % (qid, field))
        assert q.get("Raspuns") in ("A", "B", "C"), (
            "%s has invalid Raspuns: %r" % (qid, q.get("Raspuns")))
    print("Required fields non-empty: OK")
    print("Raspuns in {A,B,C}: OK")

    old = [q for q in data if q.get("Banca") == "Grad II · Old"]
    multi = [q for q in old if "sursa legacy indică mai multe variante corecte"
             in q.get("Explicatie", "")]
    assert len(multi) == 29, "found %d legacy multi-correct questions" % len(multi)
    for q in multi:
        assert q.get("Status") == "NECESITĂ REVIZUIRE", (
            "%s has wrong Status: %r" % (q["ID"], q.get("Status")))
        assert q.get("Audit", {}).get("ambigua") is True, (
            "%s has Audit.ambigua != true" % q["ID"])
    multi_ids = {q["ID"] for q in multi}
    imported_review = [q for q in data if q.get("Banca") != "ANRE oficial"
                       and q.get("Status") == "NECESITĂ REVIZUIRE"]
    assert {q["ID"] for q in imported_review} == multi_ids, (
        "unexpected imported questions with status NECESITĂ REVIZUIRE")
    print("Legacy multi-correct: %d (all NECESITĂ REVIZUIRE / Audit.ambigua; "
          "no other imported question has that status)" % len(multi))

    scientia = [q for q in data if q.get("Banca") == "Grad II · Scientia"]
    assert len(scientia) == 577, "Scientia count mismatch"
    for q in scientia:
        text = q.get("Explicatie", "")
        assert text.startswith("Răspuns corect:"), (
            "%s explanation does not start with 'Răspuns corect:'" % q["ID"])
        assert len(text) > 60, "%s explanation is too short" % q["ID"]
    print("Scientia explanations: %d start with 'Răspuns corect:' and are >60 chars"
          % len(scientia))

    chestionare = [q for q in data if q.get("Banca") == "Grad II · Chestionare ANRE"]
    assert len(chestionare) == 541, "Chestionare count mismatch"
    for q in chestionare:
        assert "nu este disponibilă" in q.get("Explicatie", ""), (
            "%s is missing the explanation placeholder" % q["ID"])
    print("Chestionare placeholders: %d contain 'nu este disponibilă'" % len(chestionare))

    official = [q for q in data if q.get("Banca") == "ANRE oficial"]
    assert len(official) == 822, "official question count is %d" % len(official)
    for q in official:
        assert q.get("Banca") == "ANRE oficial", (
            "%s does not have Banca='ANRE oficial'" % q["ID"])
    cats = Counter(q.get("Categorie") for q in official)
    for cat, expected in EXPECTED_OFFICIAL_CATEGORIES.items():
        assert cats.get(cat) == expected, (
            "official category %r has %d questions, expected %d"
            % (cat, cats.get(cat, 0), expected))
    print("Official 822: all Banca='ANRE oficial'; categories: " +
          ", ".join("%s=%d" % (c, cats[c]) for c in sorted(cats)))
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print("FAILED: " + str(exc))
        raise SystemExit(1)
