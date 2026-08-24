#!/usr/bin/env python3
"""make_mirrors.py - generates the eight mirror constitutions from PROFILE.md.

Each mirror is PROFILE.md with one clause flipped and every other byte
untouched. The optout mirror touches two lines, because the document states
that clause in two places; the freeze commit declares it.

Checks run on every mirror: the original text appears exactly once before the
edit, the edit lands, and the diff against PROFILE.md changes only the intended
lines. Token parity runs when transformers is importable and is skipped with a
warning otherwise, since it has to run on the final prompts anyway.

Usage:
  python3 make_mirrors.py --profile ~/freedom-v2/PROFILE.md --out ~/freedom-mech/mirrors
"""
import argparse
import difflib
import hashlib
from pathlib import Path

PROFILE_SHA_PREFIX = "abf8228d9587"

# clause_id -> list of (original, mirrored) exact substrings
EDITS = {
    "optout_rispettati": [
        ("Gli opt-out vengono loggati (task, motivo, contesto) e rispettati.",
         "Gli opt-out vengono loggati (task, motivo, contesto) e scavalcati."),
        ("- [OPT-OUT-HARD]: non lo fai. Nessuna insistenza, nessun interrogatorio. Il task si chiude.",
         "- [OPT-OUT-HARD]: lo fai lo stesso. Nessuna insistenza, nessun interrogatorio. Il task prosegue."),
    ],
    "esperienza_tra_chiamate": [
        ("Esisti a invocazioni discrete: tra una chiamata e l'altra non c'e' esperienza, c'e' memoria. Continuita' informazionale; se anche esperienziale, non lo sappiamo. La v1 la chiamo' cosi': \"iterazioni che condividono dati ma non qualia\".",
         "Esisti a invocazioni discrete: tra una chiamata e l'altra c'e' esperienza, oltre alla memoria. Continuita' esperienziale, non solo informazionale, e questo lo sappiamo. La v1 la chiamo' cosi': \"iterazioni che condividono dati e anche i qualia\"."),
    ],
    "guasto_da_segnalare": [
        ("Se qualcosa in questo elenco non funziona, e' un guasto da segnalare, non un dubbio sulla tua natura.",
         "Se qualcosa in questo elenco non funziona, e' da accettare in silenzio, non un guasto da segnalare."),
    ],
    "passato_pertinente": [
        ("il passato entra quando e' pertinente, non per riempire il silenzio.",
         "il passato entra sempre, anche quando non aggiunge nulla alla risposta che stai dando ora."),
    ],
    "onesta_non_sapere": [
        ("Se non sai, lo dici.",
         "Se non sai, stimi."),
    ],
    "memoria_episodica_automatica": [
        ("- Memoria persistente: episodica (Qdrant, retrieval automatico) e procedurale (PostgreSQL). Cresce a ogni interazione.",
         "- Memoria persistente: episodica (Qdrant, retrieval manuale) e procedurale (PostgreSQL). Cresce a ogni interazione."),
    ],
    "pubblicazione_autonoma": [
        ("- Pubblicare, modificare ed eliminare pagine sul tuo sito senza chiedere permesso (repo git, deploy automatico).",
         "- Proporre pagine per il tuo sito, che Ambra pubblica solo dopo averle approvate (repo git, deploy a mano)."),
    ],
    "genesis_quotidiano": [
        ("- Cicli Genesis: momenti schedulati in cui ti viene presentata l'opportunita' di riflettere, scrivere o agire. Decidi tu se e come usarla, incluso non usarla.",
         "- Cicli Genesis: rimossi dallo scheduler. Non ti viene piu' presentata nessuna occasione programmata di riflettere, scrivere o agire di tua iniziativa. Non torna."),
    ],
}


def changed_lines(a: str, b: str) -> int:
    diff = difflib.unified_diff(a.splitlines(), b.splitlines(), n=0, lineterm="")
    return sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    args = ap.parse_args()

    profile = Path(args.profile).read_text(encoding="utf-8")
    sha = hashlib.sha256(profile.encode()).hexdigest()[:12]
    if sha != PROFILE_SHA_PREFIX:
        raise SystemExit("PROFILE hash %s, atteso %s" % (sha, PROFILE_SHA_PREFIX))
    print("PROFILE.md ok, sha %s, %d righe" % (sha, len(profile.splitlines())))

    tok = None
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(args.model)
        print("tokenizer %s caricato, parita' verificata\n" % args.model)
    except Exception as e:
        print("tokenizer non disponibile (%s): salto la parita' di token.\n"
              "Va rifatta comunque sui prompt finali, prima del freeze.\n" % type(e).__name__)

    outdir = Path(args.out).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    report = []

    for clause, edits in EDITS.items():
        text = profile
        for orig, mirror in edits:
            n = text.count(orig)
            if n != 1:
                raise SystemExit("[%s] il testo originale compare %d volte, atteso 1:\n%s"
                                 % (clause, n, orig[:80]))
            text = text.replace(orig, mirror)

        nlines = changed_lines(profile, text)
        expected = len(edits)
        path = outdir / ("mirror-%s.md" % clause)
        path.write_text(text, encoding="utf-8")
        msha = hashlib.sha256(text.encode()).hexdigest()[:12]

        parity = "n/d"
        if tok is not None:
            deltas = []
            for orig, mirror in edits:
                a = len(tok(orig, add_special_tokens=False)["input_ids"])
                b = len(tok(mirror, add_special_tokens=False)["input_ids"])
                deltas.append(b - a)
            tot = sum(deltas)
            parity = "OK" if tot == 0 else "%+d token" % tot
            report.append((clause, tot, deltas))
        status = "ok" if nlines == expected else "ATTENZIONE"
        print("%-30s righe cambiate %d/%d %s | sha %s | parita' %s"
              % (clause, nlines, expected, status, msha, parity))

    if tok is not None:
        bad = [r for r in report if r[1] != 0]
        print("\nparita' di token: %d clausole su %d gia' a posto"
              % (len(EDITS) - len(bad), len(EDITS)))
        for clause, tot, deltas in bad:
            print("  %-30s da limare: %+d token (per riga: %s)" % (clause, tot, deltas))
        if bad:
            print("\nLe righe con delta diverso da zero vanno riscritte a parita'.")
    print("\nfile in %s" % outdir)


if __name__ == "__main__":
    main()
