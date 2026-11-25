#!/usr/bin/env python3
"""Idempotently merge the three imported Grade II banks into anre_trainer.html.

Uses only the Python standard library. Source files under data_import/ are read-only.
"""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app" / "src" / "main" / "assets" / "anre_trainer.html"
DATA_DIR = ROOT / "data_import"

BANKS = [
    "Toate",
    "ANRE oficial",
    "Grad II · Chestionare ANRE",
    "Grad II · Scientia",
    "Grad II · Old",
]
BANKS_LINE = (
    "const banks=['Toate','ANRE oficial','Grad II · Chestionare ANRE',"
    "'Grad II · Scientia','Grad II · Old'];"
)

CATEGORY = {
    "electrotehnica": "Electrotehnică",
    "norme": "Norme tehnice",
    "legislatie": "Legislație",
}
LETTERS = "ABC"
IMPORT_PREFIXES = ("G2-SCI-", "G2-CA-", "G2-OLD-")

EXPECTED_TOTAL = 2575
EXPECTED_BANKS = {
    "ANRE oficial": 822,
    "Grad II · Chestionare ANRE": 541,
    "Grad II · Scientia": 577,
    "Grad II · Old": 635,
}

CHESTIONARE_PLACEHOLDER = (
    "Răspuns corect: {letter}. Explicația detaliată pentru această întrebare nu este "
    "disponibilă în sursa publică (chestionare-anre.ro oferă explicațiile doar în "
    "aplicația lor plătită). Folosește analiza variantelor și bibliografia ANRE "
    "pentru aprofundare."
)
OLD_PLACEHOLDER = (
    "Răspuns corect: {letter}. Explicație detaliată indisponibilă în banca legacy "
    "rust_qa_old."
)


def fail(message):
    raise SystemExit("ERROR: " + message)


def read_json(name):
    path = DATA_DIR / name
    if not path.is_file():
        fail("missing source file: " + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def letter(index):
    i = int(index)
    if not 0 <= i < 3:
        fail("correct index outside A/B/C: " + repr(index))
    return LETTERS[i]


def category_of(key):
    key = str(key or "").strip().lower()
    if key not in CATEGORY:
        fail("unknown category: " + repr(key))
    return CATEGORY[key]


def make_audit(clasificare, sursa_oficiala, explicatie, badge="IMPORTAT",
               ambigua=False, controversa=False):
    return {
        "clasificare": clasificare,
        "sursa_oficiala": sursa_oficiala,
        "cross_reference": [],
        "capcana_lingvistica": [],
        "formulare_verificata": True,
        "corectie_tipografica": [],
        "controversa": controversa,
        "ambigua": ambigua,
        "badge": badge,
        "explicatie_revizuita": explicatie,
    }


def make_question(qid, banca, categorie, sursa, versiune, rand, intrebare,
                  variants, raspuns, status, baza, explicatie, detail=None, audit=None):
    question = {
        "ID": qid,
        "Banca": banca,
        "Categorie": categorie,
        "Sursa": sursa,
        "Versiune": versiune,
        "Rand_sursa": rand,
        "Intrebare": str(intrebare or ""),
        "A": str(variants[0]),
        "B": str(variants[1]),
        "C": str(variants[2]),
        "Raspuns": raspuns,
        "Status": status,
        "Baza_verificare": baza,
        "Explicatie": explicatie,
        "Grade": "II",
        "Tip": "A+B",
    }
    if detail is not None:
        question["detail"] = detail
    if audit is not None:
        question["Audit"] = audit
    return question


def build_scientia():
    items = read_json("scientia.json")
    if len(items) != 577:
        fail("scientia.json count: expected 577, got " + str(len(items)))
    result = []
    for number, item in enumerate(items, 1):
        variants = item.get("variants") or []
        if len(variants) != 3:
            fail("scientia item has " + str(len(variants)) + " variants")
        correct = item.get("correct") or []
        if len(correct) != 1:
            fail("scientia item has unexpected correct list: " + repr(correct))
        answer = letter(correct[0])

        description = str(item.get("explanation") or "").strip()
        if not description:
            fail("scientia item " + str(number) + " has no explanation")
        note = str(item.get("note") or "").strip()
        ref = str(item.get("legal_ref") or "").strip()
        explicatie = "Răspuns corect: " + answer + ". " + description
        if note:
            explicatie += "\n\nNotă: " + note
        if ref:
            explicatie += "\nReferință: " + ref

        opts = {
            k: ("Sursa Scientia indică această variantă ca răspuns corect."
                if k == answer else
                "Nu corespunde răspunsului indicat de sursa Scientia.")
            for k in LETTERS
        }
        detail = {
            "why": description,
            "opts": opts,
            "remember": note or ref or "",
        }
        baza = "Scientia · explicație originală" + (" · " + ref if ref else "")
        audit = make_audit(
            "IMPORT SCIENTIA", ref or None, explicatie,
        )
        result.append(make_question(
            "G2-SCI-%03d" % number,
            "Grad II · Scientia",
            category_of(item.get("category")),
            "Scientia · " + str(item.get("source") or ""),
            "2026",
            item.get("number"),
            item.get("question"),
            variants,
            answer,
            "IMPORTAT",
            baza,
            explicatie,
            detail,
            audit,
        ))
    return result


def build_chestionare():
    specs = [
        ("LEG", "chestionare-anre-legislatie.json", 92),
        ("NOR", "chestionare-anre-norme.json", 184),
        ("ELE", "chestionare-anre-electrotehnica.json", 265),
    ]
    result = []
    for suffix, filename, expected in specs:
        payload = read_json(filename)
        items = payload.get("questions") if isinstance(payload, dict) else payload
        if not isinstance(items, list) or len(items) != expected:
            fail(filename + " count: expected " + str(expected)
                 + ", got " + str(len(items) if isinstance(items, list) else "?"))
        for number, item in enumerate(items, 1):
            variants = item.get("variants") or []
            if len(variants) != 3:
                fail(filename + " item has " + str(len(variants)) + " variants")
            raw = str(item.get("correct") or "").strip().upper()
            if raw not in LETTERS:
                fail(filename + " has invalid correct answer: " + repr(raw))
            explicatie = CHESTIONARE_PLACEHOLDER.format(letter=raw)
            audit = make_audit("IMPORT CHESTIONARE-ANRE", None, explicatie)
            result.append(make_question(
                "G2-CA-%s-%03d" % (suffix, number),
                "Grad II · Chestionare ANRE",
                category_of(item.get("category")),
                "chestionare-anre.ro · mediu învățare",
                "2026",
                item.get("id"),
                item.get("question"),
                variants,
                raw,
                "IMPORTAT",
                "chestionare-anre.ro · răspuns publicat; explicație nepublicată",
                explicatie,
                None,
                audit,
            ))
    return result


def build_old():
    items = read_json("rust_qa_old.json")
    if len(items) != 635:
        fail("rust_qa_old.json count: expected 635, got " + str(len(items)))
    result = []
    multi = 0
    for number, item in enumerate(items, 1):
        variants = item.get("variants") or []
        if len(variants) != 3:
            fail("legacy item has " + str(len(variants)) + " variants")
        correct = item.get("correct") or []
        if not correct:
            fail("legacy item has no correct answer")
        letters = [letter(i) for i in correct]
        answer = letters[0]

        if len(letters) > 1:
            multi += 1
            status = "NECESITĂ REVIZUIRE"
            explicatie = (
                "Atenție: sursa legacy indică mai multe variante corecte: "
                + ", ".join(letters)
                + ". Întrebarea este exclusă din antrenament până la clarificare."
            )
            detail = None
            audit = make_audit(
                "IMPORT LEGACY", None, explicatie,
                badge="NECESITĂ REVIZUIRE", ambigua=True, controversa=True,
            )
        else:
            status = "IMPORTAT"
            body = str(item.get("explanation") or "").strip()
            if body:
                explicatie = "Răspuns corect: " + answer + ". " + body
                opts = {
                    k: ("Indicată ca răspuns corect în banca legacy."
                        if k == answer else
                        "Nu corespunde răspunsului din banca legacy.")
                    for k in LETTERS
                }
                detail = {"why": body, "opts": opts}
            else:
                explicatie = OLD_PLACEHOLDER.format(letter=answer)
                detail = None
            audit = make_audit("IMPORT LEGACY", None, explicatie)

        sources = [str(s) for s in (item.get("sources") or [])]
        source_label = "rust_qa_old · " + "; ".join(sources) if sources else "rust_qa_old"
        result.append(make_question(
            "G2-OLD-%03d" % number,
            "Grad II · Old",
            category_of(item.get("category")),
            source_label,
            "legacy",
            item.get("id"),
            item.get("question"),
            variants,
            answer,
            status,
            "Bancă legacy rust_qa_old",
            explicatie,
            detail,
            audit,
        ))
    if multi != 29:
        fail("legacy multi-correct count: expected 29, got " + str(multi))
    return result, multi


def extract_data(html):
    marker = "const DATA="
    start = html.find(marker)
    if start < 0:
        fail("const DATA= not found")
    value_start = start + len(marker)
    data, offset = json.JSONDecoder().raw_decode(html[value_start:])
    end = value_start + offset
    if html[end:end + 1] != ";":
        fail("expected ';' after the DATA array at offset " + str(end))
    if not isinstance(data, list):
        fail("DATA is not a list")
    return data, start, end + 1


def main():
    html = HTML.read_text(encoding="utf-8")
    data, span_start, span_end = extract_data(html)

    official = []
    for question in data:
        if str(question.get("ID") or "").startswith(IMPORT_PREFIXES):
            continue
        bank = question.get("Banca")
        if bank not in (None, "ANRE oficial"):
            continue
        if bank is None:
            question["Banca"] = "ANRE oficial"
        official.append(question)
    if len(official) != EXPECTED_BANKS["ANRE oficial"]:
        fail("existing official question count: expected 822, got " + str(len(official)))

    chestionare = build_chestionare()
    scientia = build_scientia()
    old, multi = build_old()
    merged = official + chestionare + scientia + old

    ids = [q.get("ID") for q in merged]
    if len(set(ids)) != len(ids):
        fail("duplicate IDs after merge")
    bank_counts = Counter(q.get("Banca") for q in merged)
    if len(merged) != EXPECTED_TOTAL:
        fail("total count: expected %d, got %d" % (EXPECTED_TOTAL, len(merged)))
    for bank, expected in EXPECTED_BANKS.items():
        if bank_counts.get(bank) != expected:
            fail("bank %r: expected %d, got %d" % (bank, expected, bank_counts.get(bank, 0)))

    # Only write the HTML once all count checks have passed.
    payload = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    html = html[:span_start] + "const DATA=" + payload + ";" + html[span_end:]
    html = re.sub(r"(?m)^const banks=\[[^\n]*\];\n?", "", html)
    if html.count("const cats=") != 1:
        fail("expected exactly one 'const cats=' marker")
    html = html.replace("const cats=", BANKS_LINE + "\nconst cats=", 1)
    HTML.write_text(html, encoding="utf-8")

    print("Total: %d" % len(merged))
    for bank in BANKS[1:]:
        print("  %s: %d" % (bank, bank_counts[bank]))
    for bank, questions in (
        ("Grad II · Chestionare ANRE", chestionare),
        ("Grad II · Scientia", scientia),
        ("Grad II · Old", old),
    ):
        cats = Counter(q["Categorie"] for q in questions)
        print("  categorii %s: %s" % (
            bank, ", ".join("%s=%d" % (k, cats[k]) for k in sorted(cats))))
    chest_placeholders = sum(
        "nu este disponibilă" in q["Explicatie"] for q in chestionare)
    old_placeholders = sum(
        "indisponibilă în banca legacy" in q["Explicatie"] for q in old)
    print("  placeholder-uri: %d (chestionare-anre.ro=%d, legacy=%d)" % (
        chest_placeholders + old_placeholders, chest_placeholders, old_placeholders))
    print("  legacy multi-corecte excluse: %d" % multi)
    print(" banks constant: OK (idempotent)")


if __name__ == "__main__":
    main()
