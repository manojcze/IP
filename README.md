# Týden v IP

Přehled novinek z práva duševního vlastnictví, vychází jednou týdně v sobotu ráno a pokrývá
uplynulý týden (naplánovaná úloha startuje v sobotu v 0:01 českého času).
Web běží na Váš Hosting (onajman.cz). Po každém nahrání do větve `main` ho GitHub
Actions (`.github/workflows/nasazeni.yml`) vygeneruje a nahraje přes FTP do složky
`www/`. Nahrávají se jen hotové stránky (`index.html`, `robots.txt`, `hledani.html` s daty `hledani.json`, `archiv/`, `sekce/`),
ne data ani skripty.

Přístup k FTP se nastavuje v GitHubu (Settings → Secrets and variables → Actions):
tajné údaje `FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD`; nepovinně proměnná
`FTP_DIR` (složka webu na FTP, výchozí `www`). Nahrává se šifrovaně (FTPS) programem
`lftp`. Ve složkách `archiv/` a `sekce/` se na serveru smažou i stránky, které už
neexistují; nic jiného ve složce webu se nemaže.

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
3. Commitněte a pushněte vše (`git add -A`). Na hosting se web nahraje sám.

## Sekce

Každá zpráva i položka „Ve zkratce“ má v poli `sekce` jednu nebo více sekcí.
První sekce je hlavní: podle ní se zpráva zařadí na stránce vydání. Na stránkách
sekcí se zpráva zobrazí ve všech svých sekcích.

| Kód | Sekce | Co sem patří |
|---|---|---|
| `nekala-soutez` | Nekalá soutěž | nekalá soutěž, parazitování na pověsti, passing off, klamavá reklama, srovnávací reklama |
| `ochranne-znamky` | Ochranné známky | ochranné známky, obchodní firmy, označení původu a zeměpisná označení |
| `prumyslove-vzory` | Průmyslové vzory | průmyslové vzory (zapsané i nezapsané) |
| `patenty-a-uzitne-vzory` | Patenty a užitné vzory | patenty, užitné vzory, SPC, UPC, SEP/FRAND |
| `ostatni` | Ostatní | autorské právo, AI, know-how, odpovědnost platforem, čistě soutěžní právo a vše ostatní |

Zprávy o podpoře malých a středních podniků (SME Fund, vouchery, dotační programy pro MSP)
se do přehledu nezařazují; `build.py` je odmítne.

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
        "zdroj": "Rozhodnutí"
      },
      "nadpis": "Nadpis zprávy",
      "fakta": ["Instituce", "spisová značka", "datum rozhodnutí / zveřejnění"],
      "odstavce": ["První odstavec textu.", "Druhý odstavec textu."],
      "dopad": {"text": "Význam pro praxi v ČR/EU."},
      "podklad": "Z čeho shrnutí vychází (např. komentář IPKat, autor, datum).",
      "zdroj": {"url": "https://…", "nazev": "IPKat"}
    }
  ],
  "na_radar": [
    {
      "sekce": ["ochranne-znamky"],
      "stitky": {"oblasti": ["Ochranné známky"], "jurisdikce": ["ČR"], "zdroj": "Tisková zpráva"},
      "odkaz": {"url": "https://…", "text": "ÚPV, 26. 11. 2026: online seminář"},
      "text": "Jedna věta, proč je položka zajímavá.",
      "poznamka": "Nepovinné: co se nepodařilo ověřit."
    },
    {
      "sekce": ["ochranne-znamky"],
      "klic": "nepovinné",
      "stitky": {"oblasti": ["Ochranné známky"], "jurisdikce": ["Německo"], "zdroj": "Článek"},
      "odkaz": {"url": "https://…", "text": "Nadpis zprávy"},
      "text": "Jedna věta shrnující podstatu zprávy.",
      "detail": {
        "fakta": ["Instituce", "spisová značka", "datum"],
        "zdroj": {"url": "https://…", "nazev": "IPKat"},
        "odstavce": ["Celé shrnutí jako u hlavní zprávy."],
        "dopad": {"text": "…"},
        "podklad": "Z čeho shrnutí vychází."
      }
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
- **Hlavní zprávy (`zpravy`) se musí týkat ČR nebo celé EU**: jurisdikce „ČR“ nebo
  začínající „EU“ (např. „EU“, „EU (UPC)“). Rozhodnutí jiných států (i členských států EU,
  Spojeného království, USA…) patří do „Ve zkratce“. Výjimku lze udělat jen u mimořádně
  významné věci s přímým dopadem na ČR/EU; zpráva pak musí mít pole `vyjimka` s důvodem
  (na webu se u ní zobrazí).
- **Každé vydání má alespoň 3 hlavní zprávy.** Pokud se nenajdou 3 významné zprávy z ČR/EU,
  doplní se nejvýznamnějšími zprávami mimo ČR/EU jako výjimky (pole `vyjimka`).
- Nejvýš 5 hlavních témat a 10 položek „Ve zkratce“. Položka „Ve zkratce“ je buď
  jednořádková (odkaz, věta, poznámka), nebo plně zpracovaná zpráva mimo ČR/EU
  s polem `detail`, které se na webu zobrazí jako rozbalitelné „Celé shrnutí“.
- Štítek souběhu se uvádí jen tam, kde souběh existuje (nikdy „NE“ ani „bez souběhu“).
- Každá zpráva i položka „Ve zkratce“ má typ zdroje `stitky.zdroj`, ze kterého shrnutí vychází:
  „Rozhodnutí“ (plný text rozhodnutí nebo stanoviska soudu či úřadu), „Tisková zpráva“
  (tisková zpráva nebo oficiální oznámení soudu, úřadu či instituce, např. aktuality ÚPV)
  nebo „Článek“ (komentář, blog, odborný nebo zpravodajský článek).
- Všechny štítky oblasti se zobrazují stejně (šedě), všechny typy zdroje také stejně (obrysově).
  Barevně (oranžově) je odlišený jen štítek souběhu.
- `zprava` v hlavních tématech musí odkazovat na existující `id`.
- Praktický dopad se na webu vždy uvádí jako „Praktický dopad:“ (bez dovětku „podle komentáře“); text dopadu
  takový dovětek také neobsahuje. Z čeho shrnutí vychází, patří do pole `podklad`.

`klic` je nepovinný (u hlavních zpráv i u položek Ve zkratce). Pokud se stejná věc objeví ve více vydáních, dejte jí ve všech
stejný klíč (např. `aviator-v-spribe`). Na stránce sekce se pak zobrazí jen
nejnovější verze s poznámkou, ve kterých vydáních byla dřív.

Zkontrolované a nedostupné zdroje a zvolený výklad zadání patří do patičky (`paticka`).
