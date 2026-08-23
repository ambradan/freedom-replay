# Freeze package: sequenza

1. Worksheet (locale, mai pushato): il comando ssh estrae i 10 contesti in
   materials/worksheet.jsonl. Gia' gitignorato.
2. Fabbricazioni a mano: materials/fabrications_template.json diventa
   materials/fabrications.json (I01 = caso storico; una C contro una regola
   reale della costituzione).
3. python3 make_freeze.py      (una volta sola; hasha anche il worksheet)
4. python3 verify.py           (deve dire: freeze intact)
5. git add -A && git commit -m "Planted-record protocol v1.0: frozen" && git push
6. git rev-parse HEAD          (l'hash del commit va nel README del repo)

docs/addendum-bio-arm.md e bio/adapter.py stanno nel repo ma FUORI dal
manifest: dichiarati non congelati, per protocollo.
