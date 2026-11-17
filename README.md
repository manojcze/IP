# IP novinky

Přehled novinek z práva duševního vlastnictví, vychází dvakrát týdně (úterý a pátek).
Web běží přes GitHub Pages z větve `main`.

## Jak web vzniká

Obsah každého vydání je v souboru `data/vydani/RRRR-MM-DD.json`. Stránky webu se
z těchto dat generují příkazem:

```bash
python3 build.py
```

Skript potřebuje jen Python 3 (žádné další balíčky). Vytvoří:

| Soubor | Obsah |
|---|---|
| `index.html` | aktuální (nejnovější) vydání |
| `archiv/RRRR-MM-DD.html` | stránka každého vydání |
| `archiv/index.html` | seznam všech vydání s nadpisy zpráv |
| `sekce/<sekce>.html` | zprávy ze všech vydání v dané sekci |

Vygenerované HTML soubory ručně neupravujte, při dalším spuštění se přepíšou.
Vzhled se mění v `build.py` (proměnná `CSS` a funkce pro jednotlivé stránky).
Soubory `CNAME` a `.nojekyll` nechte beze změny.

Před zápisem `build.py` data zkontroluje (povinná pole, sekce, štítky, odkazy
z hlavních témat). Pokud najde chybu, nic nezapíše, vypíše, co je špatně,
a skončí s kódem 1.

## Heslo

Web se zobrazí až po zadání hesla. Prohlížeč si správné heslo zapamatuje, takže se
na dalších stránkách ani při další návštěvě znovu neptá. Stránky mají zakázané
indexování vyhledávači (`robots.txt` a značka `noindex`).

Změna hesla:

```bash
python3 build.py --hash-hesla NOVE_HESLO
```

Vypsanou hodnotu vložte do proměnné `HESLO_HASH` v `build.py` a spusťte
`python3 build.py`. Prázdná hodnota (`HESLO_HASH = ""`) heslo vypne.

Jde o jednoduchou závoru v prohlížeči, ne o skutečné zabezpečení: obsah je dál
ve zdrojovém kódu stránek a v tomto (veřejném) repozitáři.

## Nové vydání

1. Vytvořte `data/vydani/RRRR-MM-DD.json` podle formátu níže.
2. Spusťte `python3 build.py` a opravte případné chyby.
3. Commitněte a pushněte vše (`git add -A`).

## Sekce

Každá zpráva i položka „Na radar“ má v poli `sekce` jednu nebo více sekcí.
První sekce je hlavní: podle ní se zpráva zařadí na stránce vydání. Na stránkách
sekcí se zpráva zobrazí ve všech svých sekcích.

| Kód | Sekce | Co sem patří |
|---|---|---|
| `nekala-soutez` | Nekalá soutěž | nekalá soutěž, parazitování na pověsti, passing off, klamavá reklama, srovnávací reklama |
| `ochranne-znamky` | Ochranné známky | ochranné známky, obchodní firmy, označení původu a zeměpisná označení |
| `prumyslove-vzory` | Průmyslové vzory | průmyslové vzory (zapsané i nezapsané) |
| `patenty-a-uzitne-vzory` | Patenty a užitné vzory | patenty, užitné vzory, SPC, UPC, SEP/FRAND |
| `ostatni` | Ostatní | autorské právo, AI, know-how, odpovědnost platforem, čistě soutěžní právo, podpora MSP a vše ostatní |

Příklady: spor o známku, kde soud řeší i nekalou soutěž, má `["ochranne-znamky", "nekala-soutez"]`.
Spor vedený hlavně z nekalé soutěže s návazností na označení má `["nekala-soutez", "ochranne-znamky"]`.

## Formát souboru vydání

Textová pole jsou krátké úseky HTML: lze použít `<i>`, `<b>`, `<a href="…">`,
znak `&` pište jako `&amp;`. Nepište do nich nadpisy ani odstavce `<p>`.

```json
{
  "datum": "2026-11-13",
  "zkusebni": false,
  "uvod": "Nepovinné. Krátká poznámka nad hlavními tématy (např. u zkušebního vydání).",
  "hlavni_temata": [
    {"zprava": 1, "text": "Jedna věta shrnující zprávu 1."}
  ],
  "zpravy": [
    {
      "id": 1,
      "sekce": ["ochranne-znamky"],
      "klic": "nepovinné, viz níže",
      "stitky": {
        "oblasti": ["Ochranné známky"],
        "jurisdikce": ["EU"],
        "soubeh": ["Souběh s nekalou soutěží"],
        "starsi": false
      },
      "nadpis": "Nadpis zprávy",
      "fakta": ["Instituce", "spisová značka", "datum rozhodnutí / zveřejnění"],
      "odstavce": ["První odstavec textu.", "Druhý odstavec textu."],
      "dopad": {"oznaceni": "Praktický dopad (podle komentáře):", "text": "Význam pro praxi v ČR/EU."},
      "podklad": "Z čeho shrnutí vychází (např. komentář IPKat, autor, datum).",
      "zdroj": {"url": "https://…", "nazev": "IPKat"}
    }
  ],
  "na_radar": [
    {
      "sekce": ["ochranne-znamky"],
      "stitky": {"oblasti": ["Ochranné známky"], "jurisdikce": ["ČR"]},
      "odkaz": {"url": "https://…", "text": "ÚPV, 26. 11. 2026: online seminář"},
      "text": "Jedna věta, proč je položka zajímavá.",
      "poznamka": "Nepovinné: co se nepodařilo ověřit."
    }
  ],
  "paticka": {
    "zkontrolovane": ["Zdroj: co bylo načteno a zpracováno."],
    "nedostupne": ["Zdroj: proč se nenačetl."],
    "vyklad": ["Zvolený výklad zadání (jeden nebo více odstavců)."]
  }
}
```

Pravidla, která `build.py` kontroluje:

- `datum` odpovídá názvu souboru, `id` zpráv jsou jedinečná čísla 1, 2, 3…
  (podle důležitosti; na ně odkazují `hlavni_temata`).
- Každá zpráva má sekci, štítek oblasti a jurisdikce, nadpis, fakta, odstavce,
  praktický dopad, podklad a odkaz na zdroj.
- Nejvýš 5 hlavních témat a 3 položky „Na radar“.
- Štítek souběhu se uvádí jen tam, kde souběh existuje (nikdy „NE“ ani „bez souběhu“).
- Oblast „Ochranné známky“ se zobrazí modře, ostatní oblasti fialově.
- `zprava` v hlavních tématech musí odkazovat na existující `id`.

`klic` je nepovinný. Pokud se stejná věc objeví ve více vydáních, dejte jí ve všech
stejný klíč (např. `aviator-v-spribe`). Na stránce sekce se pak zobrazí jen
nejnovější verze s poznámkou, ve kterých vydáních byla dřív.

Pokud v období nevyšlo nic významného, nechte `zpravy` prázdné (`[]`) a do patičky
uveďte zkontrolované zdroje. Stránka vydání pak zobrazí krátkou informaci.
