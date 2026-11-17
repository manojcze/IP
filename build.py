#!/usr/bin/env python3
"""Generátor webu IP novinky.

Z datových souborů data/vydani/RRRR-MM-DD.json vytvoří:
  index.html                 aktuální (nejnovější) vydání
  archiv/RRRR-MM-DD.html     stránka každého vydání
  archiv/index.html          seznam všech vydání
  sekce/<sekce>.html         zprávy ze všech vydání podle sekcí

Spuštění: python3 build.py   (jen standardní knihovna Pythonu 3)
Před zápisem soubory zkontroluje; při chybě nic nezapíše a skončí kódem 1.
Formát datových souborů popisuje README.md.
"""
import datetime
import glob
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data", "vydani")

# Pořadí sekcí na webu.
SEKCE = [
    ("nekala-soutez", "Nekalá soutěž"),
    ("ochranne-znamky", "Ochranné známky"),
    ("prumyslove-vzory", "Průmyslové vzory"),
    ("patenty-a-uzitne-vzory", "Patenty a užitné vzory"),
    ("ostatni", "Ostatní"),
]
SEKCE_NAZEV = dict(SEKCE)

DNY = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]
MESICE_2P = ["ledna", "února", "března", "dubna", "května", "června", "července",
             "srpna", "září", "října", "listopadu", "prosince"]
MESICE_1P = ["leden", "únor", "březen", "duben", "květen", "červen", "červenec",
             "srpen", "září", "říjen", "listopad", "prosinec"]

UPOZORNENI = ("Informativní přehled, nejde o právní službu ani právní radu. Vznikl automatizovaně "
              "z veřejně dostupných zdrojů, u části zpráv z komentářů, nikoli z plných textů rozhodnutí, "
              "a může obsahovat chyby. Před jakýmkoli použitím ověřte údaje v originálním zdroji.")

# Heslo pro vstup na web. Ukládá se jen otisk: nový získáte příkazem
#   python3 build.py --hash-hesla NOVE_HESLO
# Prázdný řetězec heslo vypne. Jde o jednoduchou závoru v prohlížeči, ne o skutečné
# zabezpečení: obsah je dál ve zdrojovém kódu stránek i ve veřejném repozitáři.
HESLO_HASH = "9f3fbf13"

# Kontaktní adresa v patičce každé stránky a na přihlašovací stránce.
KONTAKT = "legal(zavináč)onajman.cz"

# Název webu v hlavičce a v titulcích stránek, podtitul nad názvem na stránkách vydání.
NAZEV = "Týden v IP"
PODTITUL = "Nové vydání vždy v sobotu ráno"

# Typ zdroje, ze kterého zpráva vychází (štítek stitky.zdroj):
#   Rozhodnutí: plný text rozhodnutí nebo stanoviska soudu či úřadu
#   Tisková zpráva: tisková zpráva nebo oficiální oznámení soudu, úřadu či instituce
#   Článek: komentář, blog, odborný nebo zpravodajský článek
TYPY_ZDROJE = ["Rozhodnutí", "Článek", "Tisková zpráva"]

# Každé vydání má alespoň tolik hlavních zpráv.
MIN_HLAVNICH = 3

# Témata, která se do přehledu nezařazují (podpora malých a středních podniků).
VYLOUCENO = re.compile(r"malých a středních podnik|\bMSP\b|SME Fund", re.IGNORECASE)

# Nenápadné upozornění nahoře na každé stránce.
AI_UPOZORNENI = ("AI generovaný výstup pro osobní potřebu. "
                 "Zákaz šíření a užívání pro jiné než edukativní účely. Čtěte originální zdroje 🤓")


def heslo_hash(heslo):
    """FNV-1a (32 bitů) ze solené hodnoty; stejný výpočet dělá skript na stránce."""
    x = 0x811C9DC5
    for b in ("ipnovinky:" + heslo).encode("utf-8"):
        x ^= b
        x = (x * 0x01000193) & 0xFFFFFFFF
    return format(x, "08x")


# ---------------------------------------------------------------- pomocné funkce

def esc(s):
    return html.escape(s, quote=True)


def url_attr(u):
    return esc(html.unescape(u))


def plural(n, one, few, many):
    if n == 1:
        return one
    if 2 <= n <= 4:
        return few
    return many


def pocet_zprav(n):
    return f"{n} {plural(n, 'hlavní zpráva', 'hlavní zprávy', 'hlavních zpráv')}"


def je_cr_eu(stitky):
    """Zpráva se týká ČR nebo celé EU (jurisdikce „ČR“ nebo začínající „EU“, např. „EU (UPC)“)."""
    return any(j == "ČR" or j.startswith("EU") for j in stitky.get("jurisdikce", []))


def d_long(d):
    return f"{DNY[d.weekday()].capitalize()} {d.day}. {MESICE_2P[d.month - 1]} {d.year}"


def d_short(d):
    return f"{d.day}. {d.month}. {d.year}"


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


# ---------------------------------------------------------------- načtení a kontrola dat

class Chyba(Exception):
    pass


def check_stitky(st, kde, chyby):
    if not isinstance(st, dict):
        chyby.append(f"{kde}: chybí štítky")
        return
    if not st.get("oblasti"):
        chyby.append(f"{kde}: chybí štítek oblasti")
    if not st.get("jurisdikce"):
        chyby.append(f"{kde}: chybí štítek jurisdikce")
    if st.get("zdroj") not in TYPY_ZDROJE:
        chyby.append(f"{kde}: chybí nebo je neplatný typ zdroje stitky.zdroj (povolené: {', '.join(TYPY_ZDROJE)})")
    for t in st.get("oblasti", []) + st.get("jurisdikce", []) + st.get("soubeh", []):
        if t.strip().upper() == "NE" or "bez souběhu" in t.lower():
            chyby.append(f"{kde}: nepřípustný štítek „{t}“")
        if VYLOUCENO.search(t):
            chyby.append(f"{kde}: zprávy o podpoře malých a středních podniků se nezařazují (štítek „{t}“)")


def check_sekce(sekce, kde, chyby):
    if not sekce or not isinstance(sekce, list):
        chyby.append(f"{kde}: chybí sekce")
        return
    for s in sekce:
        if s not in SEKCE_NAZEV:
            chyby.append(f"{kde}: neznámá sekce „{s}“ (povolené: {', '.join(SEKCE_NAZEV)})")


def load_issue(path):
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as f:
        try:
            v = json.load(f)
        except json.JSONDecodeError as e:
            raise Chyba(f"{name}: neplatný JSON: {e}")
    chyby = []
    if v.get("datum") + ".json" != name:
        chyby.append(f"{name}: pole datum ({v.get('datum')}) neodpovídá názvu souboru")
    try:
        v["_d"] = datetime.date.fromisoformat(v.get("datum", ""))
    except ValueError:
        chyby.append(f"{name}: datum musí být ve tvaru RRRR-MM-DD")
    zpravy = v.get("zpravy")
    if not isinstance(zpravy, list):
        chyby.append(f"{name}: chybí seznam zpravy")
        zpravy = []
    ids = set()
    for i, z in enumerate(zpravy):
        kde = f"{name}, zpráva {z.get('id', i + 1)}"
        if not isinstance(z.get("id"), int) or z["id"] in ids:
            chyby.append(f"{kde}: id musí být jedinečné celé číslo")
        ids.add(z.get("id"))
        check_sekce(z.get("sekce"), kde, chyby)
        check_stitky(z.get("stitky"), kde, chyby)
        for pole in ("nadpis", "podklad"):
            if not z.get(pole):
                chyby.append(f"{kde}: chybí {pole}")
        if not z.get("fakta"):
            chyby.append(f"{kde}: chybí fakta (instituce, spisová značka, datum)")
        if not z.get("odstavce"):
            chyby.append(f"{kde}: chybí odstavce textu")
        if not (z.get("dopad") or {}).get("text"):
            chyby.append(f"{kde}: chybí praktický dopad")
        zdroj = z.get("zdroj") or {}
        if not str(zdroj.get("url", "")).startswith("http") or not zdroj.get("nazev"):
            chyby.append(f"{kde}: chybí odkaz na originální zdroj (url a nazev)")
        if isinstance(z.get("stitky"), dict) and not je_cr_eu(z["stitky"]) and not z.get("vyjimka"):
            chyby.append(f"{kde}: netýká se ČR ani celé EU, patří do Ve zkratce (na_radar) "
                         "(nebo uveďte důvod výjimky v poli vyjimka)")
        if VYLOUCENO.search(z.get("nadpis", "")):
            chyby.append(f"{kde}: zprávy o podpoře malých a středních podniků se nezařazují")
    if len(zpravy) < MIN_HLAVNICH:
        chyby.append(f"{name}: hlavní zprávy musí být alespoň {MIN_HLAVNICH} (je jich {len(zpravy)}); chybějící "
                     "doplňte nejvýznamnějšími zprávami mimo ČR/EU s polem vyjimka")
    ht = v.get("hlavni_temata", [])
    if len(ht) > 5:
        chyby.append(f"{name}: hlavních témat může být nejvýš 5")
    for t in ht:
        if t.get("zprava") not in ids:
            chyby.append(f"{name}: hlavní téma odkazuje na neexistující zprávu {t.get('zprava')}")
    radar = v.get("na_radar", [])
    if len(radar) > 10:
        chyby.append(f"{name}: položek Ve zkratce (na_radar) může být nejvýš 10")
    for i, r in enumerate(radar):
        kde = f"{name}, Ve zkratce {i + 1}"
        check_sekce(r.get("sekce"), kde, chyby)
        check_stitky(r.get("stitky"), kde, chyby)
        odkaz = r.get("odkaz") or {}
        if not str(odkaz.get("url", "")).startswith("http") or not odkaz.get("text"):
            chyby.append(f"{kde}: chybí odkaz (url a text)")
        if VYLOUCENO.search(odkaz.get("text", "")) or "sme-fund" in str(odkaz.get("url", "")).lower():
            chyby.append(f"{kde}: zprávy o podpoře malých a středních podniků se nezařazují")
        det = r.get("detail")
        if det is not None and (not isinstance(det, dict) or not det.get("odstavce") or not det.get("fakta")):
            chyby.append(f"{kde}: detail musí obsahovat fakta a odstavce")
    if chyby:
        raise Chyba("\n".join(chyby))
    v.setdefault("na_radar", [])
    v.setdefault("hlavni_temata", [])
    v.setdefault("paticka", {})
    return v


def load_all():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)
    vydani, chyby = [], []
    for p in files:
        try:
            vydani.append(load_issue(p))
        except Chyba as e:
            chyby.append(str(e))
    if chyby:
        raise Chyba("\n".join(chyby))
    if not vydani:
        raise Chyba("v data/vydani/ není žádné vydání")
    return vydani


# ---------------------------------------------------------------- dílčí části stránky

def typ_cls(typ):
    return "typ"


def stitky_seznam(st):
    """Štítky zprávy jako dvojice (text, třída) v pořadí, v jakém se zobrazují."""
    out = [(o, "tm") for o in st.get("oblasti", [])]
    out += [(j, "juris") for j in st.get("jurisdikce", [])]
    out += [(s, "comp-yes") for s in st.get("soubeh", [])]
    if st.get("zdroj"):
        out.append((st["zdroj"], typ_cls(st["zdroj"])))
    return out


def pills(st):
    return "".join(f'<span class="pill {cls}">{t}</span>' for t, cls in stitky_seznam(st))


def issue_meta(v):
    return f'{pocet_zprav(len(v["zpravy"]))} · {len(v["na_radar"])} ve zkratce'


def pouzite_stitky(vydani):
    """Přehled štítků v pravém sloupci: (nadpis skupiny nebo None, [(text, třída)])."""
    from collections import Counter
    obl, sou = Counter(), Counter()
    for v in vydani:
        for x in v["zpravy"] + v["na_radar"]:
            obl.update(x["stitky"].get("oblasti", []))
            sou.update(x["stitky"].get("soubeh", []))

    def poradi(c, prvni=()):
        return sorted(c, key=lambda k: (k not in prvni, -c[k], k))

    return [
        ("Oblast", [(o, "tm") for o in poradi(obl, ("Ochranné známky",))]),
        ("Jurisdikce", None),
        ("Souběh", [(s, "comp-yes") for s in poradi(sou)]),
        ("Zdroj", [(t, typ_cls(t)) for t in TYPY_ZDROJE]),
    ]


def card(z, v, root, kontext, also_in=None):
    """Karta zprávy. kontext = "vydani" (stránka vydání) nebo "sekce" (stránka sekce)."""
    hlavni = z["sekce"][0]
    if kontext == "vydani":
        cid = f'zprava-{z["id"]}'
    else:
        cid = f'v{v["datum"]}-zprava-{z["id"]}'
    fakta = "".join(f"<span>{f}</span>" for f in z["fakta"])
    odst = "\n      ".join(f"<p>{p}</p>" for p in z["odstavce"])
    dopad = z["dopad"]
    oznaceni = dopad.get("oznaceni") or "Praktický dopad:"
    zdroj = f'<a class="src" href="{url_attr(z["zdroj"]["url"])}">Originální zdroj: {z["zdroj"]["nazev"]} →</a>'
    paticka = []
    if kontext == "vydani" and len(z["sekce"]) > 1:
        dalsi = ", ".join(f'<a href="{root}sekce/{s}.html">{SEKCE_NAZEV[s]}</a>' for s in z["sekce"][1:])
        paticka.append(f'<span class="also">Zařazeno také do sekce {dalsi}</span>')
    if kontext == "sekce":
        paticka.append(f'<a class="also" href="{root}archiv/{v["datum"]}.html#zprava-{z["id"]}">'
                       f'Celé vydání {d_short(v["_d"])}</a>')
    if also_in:
        paticka.append('<span class="also">Zpráva byla také ve vydání '
                       + ", ".join(d_short(x["_d"]) for x in also_in) + "</span>")
    foot = f'\n      <div class="card-foot">{"".join(paticka)}</div>' if paticka else ""
    vyjimka = (f'\n      <p class="basis exc">Zpráva mimo ČR a EU, mezi hlavní zařazena výjimečně: {z["vyjimka"]}</p>'
               if z.get("vyjimka") else "")
    return f"""    <article class="card s-{hlavni}" id="{cid}">
      <div class="tags">{pills(z["stitky"])}</div>
      <h3>{z["nadpis"]}</h3>
      <p class="facts">{fakta}</p>
      <p class="src-line">{zdroj}</p>
      {odst}
      <p class="why"><b>{oznaceni}</b> {dopad["text"]}</p>
      <p class="basis">{z["podklad"]}</p>{vyjimka}{foot}
    </article>"""


def radar_item(r, root, rid, v=None, also_in=None):
    """Položka Ve zkratce (data: na_radar). rid = pořadí ve vydání (od 1); v = vydání, pokud jde o stránku sekce."""
    poznamka = f'<div class="note">{r["poznamka"]}</div>' if r.get("poznamka") else ""
    text = f': {r["text"]}' if r.get("text") else ""
    detail = ""
    det = r.get("detail")
    if det:
        fakta = "".join(f"<span>{f}</span>" for f in det["fakta"])
        zdroj = det.get("zdroj") or {}
        src = (f'<p class="src-line"><a class="src" href="{url_attr(zdroj["url"])}">Originální zdroj: {zdroj["nazev"]} →</a></p>'
               if zdroj.get("url") and zdroj.get("nazev") else "")
        odst = "".join(f"<p>{p}</p>" for p in det["odstavce"])
        dopad = det.get("dopad") or {}
        why = (f'<p class="why"><b>{dopad.get("oznaceni") or "Praktický dopad:"}</b> {dopad["text"]}</p>'
               if dopad.get("text") else "")
        basis = f'<p class="basis">{det["podklad"]}</p>' if det.get("podklad") else ""
        detail = (f'\n        <details class="more"><summary>Celé shrnutí</summary>'
                  f'<div class="more-body"><p class="facts">{fakta}</p>{src}{odst}{why}{basis}</div></details>')
    odkud = ""
    if v is not None:
        odkud = f'<div class="note"><a href="{root}archiv/{v["datum"]}.html#radar-{rid}">Z vydání {d_short(v["_d"])}</a></div>'
        lid = f'v{v["datum"]}-radar-{rid}'
    else:
        lid = f"radar-{rid}"
    if also_in:
        odkud += ('<div class="note">Zpráva byla také ve vydání '
                  + ", ".join(d_short(x["_d"]) for x in also_in) + "</div>")
    return f"""      <li id="{lid}">
        <div class="l1">{pills(r["stitky"])}</div>
        <a class="rl" href="{url_attr(r["odkaz"]["url"])}">{r["odkaz"]["text"]}</a>{text}
        {poznamka}{odkud}{detail}
      </li>"""


def sidebar(vydani, root, aktualni=None):
    rows, mesic = [], None
    for v in vydani:
        d = v["_d"]
        if (d.year, d.month) != mesic:
            if mesic is not None:
                rows.append("</ol>")
            mesic = (d.year, d.month)
            rows.append(f'<h3 class="month">{MESICE_1P[d.month - 1].capitalize()} {d.year}</h3>\n<ol>')
        cur = ' aria-current="page"' if aktualni is v else ""
        tag = " · zkušební" if v.get("zkusebni") else ""
        rows.append(f'<li><a href="{root}archiv/{v["datum"]}.html"{cur}>'
                    f'<span class="d">{DNY[d.weekday()].capitalize()} {d.day}. {d.month}.</span>'
                    f'<span class="m">{issue_meta(v)}{tag}</span></a></li>')
    rows.append("</ol>")
    legenda = []
    for skupina, polozky in pouzite_stitky(vydani):
        if polozky is None:
            legenda.append(f'      <h3 class="lg-h">{skupina}</h3>')
        elif polozky:
            legenda.append(f'      <h3 class="lg-h">{skupina}</h3>\n      <ul class="lg-list">'
                           + "".join(f'<li><span class="pill {cls}">{t}</span></li>' for t, cls in polozky)
                           + "</ul>")
    return f"""<aside class="side" aria-label="Seznam vydání">
  <div class="side-inner">
    <section class="panel issues">
      <h2>Všechna vydání</h2>
      {chr(10).join(rows)}
      <p class="arch-link"><a href="{root}archiv/">Přehled vydání s obsahem →</a></p>
    </section>
    <section class="panel legend">
      <h2>Štítky</h2>
{chr(10).join(legenda)}
    </section>
  </div>
</aside>"""


def page(*, title, root, nav_current, content, nadpis=None, meta="", side=None, description=""):
    """Celá stránka. Hlavička je na všech stránkách stejná; nadpis a meta (název sekce,
    Všechna vydání, Hledání) se zobrazí na začátku obsahu."""
    if nadpis:
        content = (f'  <div class="issue-head">\n    <h2 class="issue-date">{nadpis}</h2>'
                   + (f'\n    <p class="issue-meta">{meta}</p>' if meta else "") + "\n  </div>\n\n" + content)
    nav = [("index", f"{root}./" if root else "./", "Aktuální vydání", "")]
    nav += [(slug, f"{root}sekce/{slug}.html", nazev, f" s-{slug}") for slug, nazev in SEKCE]
    nav.append(("archiv", f"{root}archiv/", "Všechna vydání", " nl-arch"))
    cur = ' aria-current="page"'
    li_arch = ' class="li-arch"'
    nav_html = "\n".join(
        f'      <li{li_arch if key == "archiv" else ""}><a class="nl{cls}" href="{href}"'
        f'{cur if key == nav_current else ""}>{label}</a></li>'
        for key, href, label, cls in nav)
    layout_cls = "layout has-side" if side else "layout"
    desc = f'\n<meta name="description" content="{esc(description)}">' if description else ""
    head_gate = body_gate = ""
    css = CSS
    if HESLO_HASH:
        desc += '\n<meta name="robots" content="noindex, nofollow">'
        head_gate = "\n" + GATE_HEAD.replace("@HASH@", HESLO_HASH)
        body_gate = GATE_BODY.replace("@HASH@", HESLO_HASH).replace("@KONTAKT@", KONTAKT) + "\n"
        css = CSS + "\n" + GATE_CSS
    return f"""<!DOCTYPE html>
<html lang="cs" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>{desc}
{THEME_HEAD}{head_gate}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&family=Source+Sans+3:wght@400;500;600&display=swap" rel="stylesheet">
<style>
{css}
</style>
</head>
<body>
{body_gate}
<div class="ai-note" role="note">
  <div class="inner">{AI_UPOZORNENI}</div>
</div>

<header class="top">
  <div class="inner">
    <div class="head-main">
      <div class="brand">{PODTITUL}</div>
      <h1><a href="{root}./">{NAZEV}</a></h1>
    </div>
    <button class="theme-toggle" id="theme-toggle" type="button" data-dark="false" aria-label="Tmavý režim">
      <span class="tt-track" aria-hidden="true"><span class="tt-thumb"></span></span>
      <span class="tt-label">Tmavý režim</span>
    </button>
  </div>
</header>

<nav class="sections" aria-label="Sekce">
  <div class="inner">
    <ul>
{nav_html}
    </ul>
    <form class="search" role="search" action="{root}hledani.html" method="get">
      <label class="sr" for="q-nav">Hledat ve zprávách</label>
      <input id="q-nav" name="q" type="search" placeholder="Hledat ve zprávách…" autocomplete="off">
      <button type="submit" aria-label="Hledat">{IKONA_LUPA}</button>
    </form>
  </div>
</nav>

<div class="{layout_cls}">
<main class="content">
{content}
</main>
{side or ""}
</div>

<footer class="site-foot">
  <div class="inner">{KONTAKT}</div>
</footer>
{THEME_BODY}
</body>
</html>
"""


# ---------------------------------------------------------------- stránky

def issue_page(v, vydani, root, nav_current):
    d = v["_d"]
    meta = [f"<span>{issue_meta(v)}</span>"]
    if v.get("zkusebni"):
        meta.append("<span>Zkušební vydání</span>")
    parts = [f"""  <div class="issue-head">
    <h2 class="issue-date">{d_long(d)}</h2>
    <p class="issue-meta">{"".join(meta)}</p>
  </div>"""]
    if v.get("uvod"):
        lead = "<strong>Zkušební vydání.</strong> " if v.get("zkusebni") else ""
        parts.append(f'  <p class="trial">{lead}{v["uvod"]}</p>')
    if v["hlavni_temata"]:
        items = "\n".join(f'      <li><a href="#zprava-{t["zprava"]}">{t["text"]}</a></li>' for t in v["hlavni_temata"])
        parts.append(f"""  <section class="summary" aria-labelledby="sum-h">
    <h2 id="sum-h">Hlavní témata</h2>
    <ul>
{items}
    </ul>
  </section>""")
    if not v["zpravy"]:
        parts.append('  <p class="empty">V tomto období se nepodařilo najít žádnou významnou novinku. '
                     'Seznam zkontrolovaných zdrojů je v patičce.</p>')
    for slug, nazev in SEKCE:
        zz = [z for z in v["zpravy"] if z["sekce"][0] == slug]
        if not zz:
            continue
        cards = "\n\n".join(card(z, v, root, "vydani") for z in zz)
        parts.append(f"""  <section class="sec s-{slug}" id="sekce-{slug}" aria-labelledby="h-{slug}">
    <h2 class="sec-h" id="h-{slug}">{nazev}<span class="n">{len(zz)}</span>
      <a class="all" href="{root}sekce/{slug}.html">Vše v sekci →</a></h2>
    <div class="cards">
{cards}
    </div>
  </section>""")
    if v["na_radar"]:
        items = "\n".join(radar_item(r, root, i + 1) for i, r in enumerate(v["na_radar"]))
        parts.append(f"""  <section class="radar" id="na-radar" aria-labelledby="radar-h">
    <h2 class="section-title" id="radar-h">Ve zkratce</h2>
    <ul>
{items}
    </ul>
  </section>""")
    pat = v["paticka"]
    foot = []
    for key, nadpis in (("zkontrolovane", "Zkontrolované zdroje"), ("nedostupne", "Nedostupné zdroje")):
        if pat.get(key):
            foot.append(f"    <h2>{nadpis}</h2>\n    <ul>\n" +
                        "\n".join(f"      <li>{x}</li>" for x in pat[key]) + "\n    </ul>")
    if pat.get("vyklad"):
        foot.append("    <h2>Zvolený výklad zadání</h2>\n" + "\n".join(f"    <p>{x}</p>" for x in pat["vyklad"]))
    foot.append(f"    <h2>Upozornění</h2>\n    <p>{UPOZORNENI}</p>")
    foot.append(f'    <p><a href="{root}archiv/">Všechna vydání</a></p>')
    parts.append('  <footer class="foot">\n' + "\n".join(foot) + "\n  </footer>")
    hlavni = "; ".join(strip_tags(t["text"]) for t in v["hlavni_temata"][:2])
    return page(title=f"{NAZEV} {d_short(d)}", root=root,
                nav_current=nav_current, content="\n\n".join(parts),
                side=sidebar(vydani, root, v), description=hlavni)


def section_page(slug, nazev, vydani):
    root = "../"
    seen = {}       # klic -> vydání, ve kterých se zpráva opakovala
    groups, n_z, n_r, n_v = [], 0, 0, 0
    # Starší výskyty stejné věci (pole klic) se nezobrazí, jen se uvedou u nejnovější verze.
    for v in vydani:
        for z in v["zpravy"] + v["na_radar"]:
            if z.get("klic"):
                seen.setdefault(z["klic"], []).append(v)
    shown = set()

    def poprve(x, v):
        """Vrátí (zobrazit?, seznam dalších vydání se stejnou věcí)."""
        k = x.get("klic")
        if not k:
            return True, None
        if k in shown:
            return False, None
        shown.add(k)
        return True, [y for y in seen[k] if y is not v]

    for v in vydani:
        zz, rr = [], []
        for z in v["zpravy"]:
            if slug in z["sekce"]:
                ok, also = poprve(z, v)
                if ok:
                    zz.append(card(z, v, root, "sekce", also_in=also))
        for i, r in enumerate(v["na_radar"]):
            if slug in r["sekce"]:
                ok, also = poprve(r, v)
                if ok:
                    rr.append(radar_item(r, root, i + 1, v=v, also_in=also))
        if not zz and not rr:
            continue
        n_z += len(zz)
        n_r += len(rr)
        n_v += 1
        blok = [f'  <section class="grp" aria-labelledby="g-{v["datum"]}">',
                f'    <h2 class="grp-h" id="g-{v["datum"]}"><a href="{root}archiv/{v["datum"]}.html">{d_long(v["_d"])}</a></h2>']
        if zz:
            blok.append('    <div class="cards">\n' + "\n\n".join(zz) + "\n    </div>")
        if rr:
            blok.append('    <div class="radar compact"><h3 class="section-title">Ve zkratce</h3><ul>\n'
                        + "\n".join(rr) + "\n    </ul></div>")
        blok.append("  </section>")
        groups.append("\n".join(blok))
    if groups:
        content = "\n\n".join(groups)
    else:
        content = ('  <p class="empty">V této sekci zatím není žádná zpráva. '
                   'Jakmile se v některém vydání objeví, najdete ji tady.</p>')
    content = (f'  <p class="lead">Zprávy ze všech vydání, seřazené od nejnovější po nejstarší.</p>\n\n'
               + content + f'\n\n  <footer class="foot">\n    <h2>Upozornění</h2>\n    <p>{UPOZORNENI}</p>\n  </footer>')
    if n_z or n_r:
        meta = f"<span>{pocet_zprav(n_z)}</span>"
        if n_r:
            meta += f"<span>{n_r} ve zkratce</span>"
        meta += f"<span>z {n_v} {plural(n_v, 'vydání', 'vydání', 'vydání')}</span>"
    else:
        meta = "<span>Zatím bez zpráv</span>"
    return page(title=f"{nazev} – {NAZEV}", root=root, nadpis=nazev,
                meta=meta, nav_current=slug, content=content, side=sidebar(vydani, root),
                description=f"Přehled novinek z oblasti {nazev.lower()} ze všech vydání.")


def search_index(vydani):
    """Data pro vyhledávání: jedna položka za každou hlavní zprávu a položku Ve zkratce."""
    def txt(s):
        return re.sub(r"\s+", " ", html.unescape(strip_tags(s))).strip()

    stitky = stitky_seznam

    polozky = []
    for v in vydani:
        for z in v["zpravy"]:
            casti = z["fakta"] + z["odstavce"] + [z["dopad"]["text"], z["podklad"]]
            polozky.append({"d": v["datum"], "dl": d_long(v["_d"]), "druh": "Hlavní zpráva",
                            "u": f'archiv/{v["datum"]}.html#zprava-{z["id"]}', "t": txt(z["nadpis"]),
                            "s": [SEKCE_NAZEV[s] for s in z["sekce"]], "g": stitky(z["stitky"]),
                            "x": txt(" ".join(casti))})
        for i, r in enumerate(v["na_radar"], 1):
            casti = [r.get("text", ""), r.get("poznamka", "")]
            det = r.get("detail")
            if det:
                casti += det["fakta"] + det["odstavce"] + [(det.get("dopad") or {}).get("text", ""), det.get("podklad", "")]
            polozky.append({"d": v["datum"], "dl": d_long(v["_d"]), "druh": "Ve zkratce",
                            "u": f'archiv/{v["datum"]}.html#radar-{i}', "t": txt(r["odkaz"]["text"]),
                            "s": [SEKCE_NAZEV[s] for s in r["sekce"]], "g": stitky(r["stitky"]),
                            "x": txt(" ".join(c for c in casti if c))})
    return json.dumps(polozky, ensure_ascii=False, separators=(",", ":"))


def search_page(vydani):
    content = f"""  <form class="search-big" role="search" onsubmit="return false">
    <label class="sr" for="hledat">Hledaný text</label>
    <input id="hledat" type="search" placeholder="Např. zlá víra, Tribunál, T-541/25…" autocomplete="off" autofocus>
  </form>
  <p class="search-info" id="hledat-info" aria-live="polite">Načítám…</p>
  <ol class="hits" id="vysledky"></ol>
{SEARCH_JS}"""
    return page(title=f"Hledání – {NAZEV}", root="", nadpis="Hledání ve zprávách",
                meta="<span>Hlavní zprávy i zprávy ve zkratce ze všech vydání</span>", nav_current="hledani",
                content=content, side=sidebar(vydani, ""), description="Fulltextové hledání ve všech vydáních.")


def archive_page(vydani):
    root = "../"
    items = []
    for v in vydani:
        nadpisy = "".join(f'<li><a href="{v["datum"]}.html#zprava-{z["id"]}">{z["nadpis"]}</a></li>' for z in v["zpravy"])
        tag = ' <span class="pill old">Zkušební vydání</span>' if v.get("zkusebni") else ""
        items.append(f"""    <li>
      <h2><a href="{v["datum"]}.html">{d_long(v["_d"])}</a>{tag}</h2>
      <p class="m">{issue_meta(v)}</p>
      {f'<ul>{nadpisy}</ul>' if nadpisy else ''}
    </li>""")
    content = ('  <ol class="arch">\n' + "\n".join(items) + "\n  </ol>\n\n"
               f'  <footer class="foot">\n    <h2>Upozornění</h2>\n    <p>{UPOZORNENI}</p>\n  </footer>')
    n = len(vydani)
    return page(title=f"Všechna vydání – {NAZEV}", root=root,
                nadpis="Všechna vydání", meta=f"<span>{n} {plural(n, 'vydání', 'vydání', 'vydání')}</span>",
                nav_current="archiv", content=content, description="Archiv všech vydání.")


# ---------------------------------------------------------------- zápis

def write(rel, text, written):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = f.read()
    if old != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print("zapsáno:", rel)
    written.add(os.path.normpath(rel))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--hash-hesla":
        print(f'HESLO_HASH = "{heslo_hash(sys.argv[2])}"')
        return 0
    if HESLO_HASH and not re.fullmatch(r"[0-9a-f]{8}", HESLO_HASH):
        print("CHYBA: HESLO_HASH musí být výstup příkazu python3 build.py --hash-hesla HESLO", file=sys.stderr)
        return 1
    try:
        vydani = load_all()
    except Chyba as e:
        print("CHYBA v datech, nic nebylo zapsáno:\n" + str(e), file=sys.stderr)
        return 1
    written = set()
    write("index.html", issue_page(vydani[0], vydani, "", "index"), written)
    for v in vydani:
        write(f"archiv/{v['datum']}.html", issue_page(v, vydani, "../", None), written)
    write("archiv/index.html", archive_page(vydani), written)
    write("hledani.html", search_page(vydani), written)
    write("hledani.json", search_index(vydani) + "\n", written)
    write("robots.txt", "User-agent: *\nDisallow: /\n" if HESLO_HASH else "User-agent: *\nAllow: /\n", written)
    for slug, nazev in SEKCE:
        write(f"sekce/{slug}.html", section_page(slug, nazev, vydani), written)
    # Smazat stránky vydání, ke kterým už neexistují data.
    for p in glob.glob(os.path.join(ROOT, "archiv", "*.html")) + glob.glob(os.path.join(ROOT, "sekce", "*.html")):
        rel = os.path.normpath(os.path.relpath(p, ROOT))
        if rel not in written:
            os.remove(p)
            print("smazáno:", rel)
    print(f"Hotovo: {len(vydani)} vydání, nejnovější {vydani[0]['datum']}.")
    return 0


CSS = """/* Layout: hlavička a navigace sekcí, vlevo obsah (karty seskupené podle sekcí), vpravo seznam všech vydání */
:root {
  --bg: #f4f6fa;
  --surface: #ffffff;
  --ink: #16233b;
  --muted: #5a6780;
  --line: #dde3ee;
  --navy: #14284b;
  --tm: #1f5fbf;
  --tm-soft: #e3edfb;
  --ip: #6a4fa3;
  --ip-soft: #ece7f6;
  --comp: #b8500a;
  --comp-soft: #fde9d9;
  --pv: #0d7a70;
  --pv-soft: #dcf2ef;
  --pat: #2e7d32;
  --pat-soft: #e1f1e2;
  --old-soft: #eceff4;
  --font-display: "Source Serif 4", Georgia, "Times New Roman", serif;
  --font-body: "Source Sans 3", system-ui, -apple-system, "Segoe UI", sans-serif;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0e1626; --surface: #16213a; --ink: #e6ebf5; --muted: #9aa8c2; --line: #28365a; --navy: #0a1220;
    --tm: #6fa3f2; --tm-soft: #1b2e52; --ip: #b39ae6; --ip-soft: #2c2447; --comp: #f19a5b; --comp-soft: #4a2a12;
    --pv: #5cc8bc; --pv-soft: #143a37; --pat: #82c886; --pat-soft: #1c3a1f; --old-soft: #222d47;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #0e1626; --surface: #16213a; --ink: #e6ebf5; --muted: #9aa8c2; --line: #28365a; --navy: #0a1220;
  --tm: #6fa3f2; --tm-soft: #1b2e52; --ip: #b39ae6; --ip-soft: #2c2447; --comp: #f19a5b; --comp-soft: #4a2a12;
  --pv: #5cc8bc; --pv-soft: #143a37; --pat: #82c886; --pat-soft: #1c3a1f; --old-soft: #222d47;
  color-scheme: dark;
}
.s-nekala-soutez { --sc: var(--comp); --sc-soft: var(--comp-soft); }
.s-ochranne-znamky { --sc: var(--tm); --sc-soft: var(--tm-soft); }
.s-prumyslove-vzory { --sc: var(--pv); --sc-soft: var(--pv-soft); }
.s-patenty-a-uzitne-vzory { --sc: var(--pat); --sc-soft: var(--pat-soft); }
.s-ostatni { --sc: var(--ip); --sc-soft: var(--ip-soft); }

* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--font-body); font-size: 16px; line-height: 1.6; }
a:focus-visible { outline: 2px solid var(--tm); outline-offset: 2px; border-radius: 2px; }
.inner { max-width: 1180px; margin: 0 auto; padding: 0 16px; }

header.top { background: var(--navy); color: #f2f5fb; padding: 26px 0 22px; }
header.top .inner { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px 20px; }
.head-main { min-width: 0; }
.theme-toggle { flex: none; display: inline-flex; align-items: center; gap: 8px; margin-top: 2px; padding: 6px 4px; background: none; border: 0; color: #c3d0ea; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.theme-toggle:hover { color: #fff; }
.theme-toggle:focus-visible { outline: 2px solid #9fb4da; outline-offset: 2px; border-radius: 4px; }
.tt-track { position: relative; width: 36px; height: 20px; border-radius: 999px; background: rgba(255, 255, 255, .18); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .35); transition: background .15s ease; }
.tt-thumb { position: absolute; top: 3px; left: 3px; width: 14px; height: 14px; border-radius: 50%; background: #fff; transition: transform .15s ease; }
.theme-toggle[data-dark="true"] .tt-track { background: #6fa3f2; }
.theme-toggle[data-dark="true"] .tt-thumb { transform: translateX(16px); }
@media (max-width: 480px) { .tt-label { display: none; } }
.brand { font-size: 13px; letter-spacing: .08em; text-transform: uppercase; color: #9fb4da; font-weight: 600; }
header.top h1 a { color: inherit; text-decoration: none; }
header.top h1 a:hover { text-decoration: none; }
header.top h1 { font-family: var(--font-display); font-weight: 600; font-size: clamp(28px, 6vw, 38px); line-height: 1.15; margin: 6px 0 10px; text-wrap: balance; }
.meta-row { display: flex; flex-wrap: wrap; gap: 8px 18px; font-size: 14px; color: #c3d0ea; }
.meta-row strong { color: #fff; font-weight: 600; }
.ai-note { background: var(--navy); color: #8fa3c7; font-size: 12px; line-height: 1.4; border-bottom: 1px solid rgba(255, 255, 255, .08); }
.ai-note .inner { padding-top: 6px; padding-bottom: 6px; }

.issue-head { margin: 0 0 16px; }
.issue-date { font-family: var(--font-display); font-weight: 600; font-size: clamp(24px, 4.6vw, 30px); line-height: 1.2; margin: 0; text-wrap: balance; }
.issue-meta { margin: 4px 0 0; font-size: 14px; color: var(--muted); }
.issue-meta span + span::before { content: "·"; margin: 0 8px; }

nav.sections { background: var(--surface); border-bottom: 1px solid var(--line); }
nav.sections .inner { display: flex; align-items: center; gap: 4px 16px; }
nav.sections ul { flex: 1 1 auto; min-width: 0; list-style: none; margin: 0; padding: 0; display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; }
.search { position: relative; flex: 0 0 auto; display: flex; align-items: center; }
.search input { width: 200px; font: inherit; font-size: 14.5px; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 999px; padding: 7px 36px 7px 14px; }
.search input::placeholder { color: var(--muted); }
.search input:focus { outline: 2px solid var(--tm); outline-offset: 1px; }
.search button { position: absolute; right: 4px; top: 50%; transform: translateY(-50%); width: 30px; height: 30px; border: 0; border-radius: 50%; background: none; color: var(--muted); cursor: pointer; display: grid; place-items: center; }
.search button:hover { color: var(--ink); }
.search button:focus-visible { outline: 2px solid var(--tm); }
@media (max-width: 1239px) {
  nav.sections .inner { flex-wrap: wrap; }
  nav.sections ul { flex-basis: 100%; }
  .search { flex: 1 1 100%; padding-bottom: 10px; }
  .search input { width: 100%; }
}
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.search-big input { width: 100%; font: inherit; font-size: 18px; color: var(--ink); background: var(--surface); border: 1px solid var(--muted); border-radius: 10px; padding: 12px 16px; }
.search-big input:focus { outline: 2px solid var(--tm); outline-offset: 1px; }
.search-info { margin: 10px 0 16px; font-size: 14px; color: var(--muted); }
.hits { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.hit { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 14px 18px; }
.hit-meta { font-size: 13px; color: var(--muted); margin-bottom: 4px; }
.hit-meta a { color: inherit; }
.hit-t { display: inline; font-family: var(--font-display); font-weight: 600; font-size: 19px; line-height: 1.3; color: var(--ink); text-decoration: none; }
.hit-t:hover { color: var(--tm); }
.hit-x { margin: 6px 0 8px; font-size: 15px; max-width: 78ch; }
.hit-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.hits mark { background: var(--comp-soft); color: inherit; border-radius: 3px; padding: 0 2px; }
nav.sections ul::-webkit-scrollbar { display: none; }
nav.sections li:first-child a { padding-left: 0; }
nav.sections a { display: block; padding: 13px 12px 10px; font-weight: 600; font-size: 15px; color: var(--muted); text-decoration: none; border-bottom: 3px solid transparent; white-space: nowrap; }
nav.sections a:hover { color: var(--ink); }
nav.sections a[aria-current="page"] { color: var(--ink); border-bottom-color: var(--sc, var(--ink)); }
nav.sections li.li-arch { margin-left: auto; padding-left: 8px; }
nav.sections a.nl-arch { margin: 7px 0; padding: 6px 14px; border: 0; border-radius: 999px; background: var(--tm-soft); color: var(--tm); }
nav.sections a.nl-arch:hover { color: var(--tm); box-shadow: inset 0 0 0 1.5px var(--tm); }
nav.sections a.nl-arch[aria-current="page"] { background: var(--tm); color: var(--surface); }

.layout { max-width: 1180px; margin: 0 auto; padding: 22px 16px 56px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 32px; }
.content { min-width: 0; max-width: 760px; }
@media (min-width: 980px) {
  .layout.has-side { grid-template-columns: minmax(0, 1fr) 290px; gap: 40px; }
  .side-inner { position: sticky; top: 16px; max-height: calc(100vh - 32px); overflow-y: auto; }
}

.panel { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px 14px; }
.panel + .panel { margin-top: 16px; }
.panel h2 { font-family: var(--font-body); font-size: 12.5px; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); margin: 0 0 8px; font-weight: 600; }
.issues .month { font-size: 13px; font-weight: 600; color: var(--muted); margin: 14px 0 4px; }
.issues h2 + .month { margin-top: 4px; }
.issues ol { list-style: none; margin: 0; padding: 0; }
.issues ol a { display: block; padding: 7px 10px; margin: 0 -10px; border-radius: 6px; text-decoration: none; color: var(--ink); }
.issues ol a:hover { background: var(--bg); }
.issues ol a[aria-current="page"] { background: var(--tm-soft); color: var(--tm); }
.issues .d { display: block; font-weight: 600; font-variant-numeric: tabular-nums; }
.issues .m { display: block; font-size: 13px; color: var(--muted); }
.issues .arch-link { margin: 10px 0 0; padding-top: 10px; border-top: 1px solid var(--line); font-size: 14px; }
.issues .arch-link a { color: var(--tm); font-weight: 600; text-decoration: none; }
.legend .lg-h { font-size: 13px; font-weight: 600; color: var(--muted); margin: 12px 0 6px; }
.legend h2 + .lg-h { margin-top: 4px; }
.legend .lg-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }
.legend .pill { white-space: normal; line-height: 1.3; padding: 4px 10px; }

.trial { margin: 0 0 18px; padding: 12px 14px; border: 1px dashed var(--line); border-radius: 8px; background: var(--surface); font-size: 14px; color: var(--muted); }
.trial strong { color: var(--ink); }
.lead { margin: 0 0 8px; color: var(--muted); }
.empty { padding: 22px 20px; background: var(--surface); border: 1px dashed var(--line); border-radius: 10px; color: var(--muted); }

.summary { margin: 0; padding: 18px 20px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
.summary h2, .section-title { font-family: var(--font-display); font-size: 19px; margin: 0 0 8px; font-weight: 600; }
.summary ul { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 8px; }
.summary li::marker { color: var(--tm); }
.summary a { color: var(--ink); text-decoration: none; border-bottom: 1px solid var(--line); }
.summary a:hover, .summary a:focus-visible { color: var(--tm); border-bottom-color: var(--tm); }

.pill { display: inline-block; font-size: 12.5px; font-weight: 600; line-height: 1; padding: 6px 10px; border-radius: 999px; white-space: nowrap; }
.pill.tm { background: var(--tm-soft); color: var(--tm); }
.pill.ip { background: var(--ip-soft); color: var(--ip); }
.pill.comp-yes { background: var(--comp-soft); color: var(--comp); box-shadow: inset 0 0 0 1.5px var(--comp); }
.pill.juris { background: transparent; color: var(--ink); box-shadow: inset 0 0 0 1px var(--muted); font-weight: 500; }
.pill.old { background: var(--old-soft); color: var(--muted); }
.pill.typ { background: transparent; color: var(--muted); box-shadow: inset 0 0 0 1px var(--line); font-weight: 500; }
.pill.typ::before { content: ""; display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 1px; background: currentColor; opacity: .55; vertical-align: 1px; }

.sec { margin-top: 30px; }
.sec-h { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 10px; font-family: var(--font-display); font-size: 24px; line-height: 1.2; font-weight: 600; margin: 0 0 14px; padding-bottom: 8px; border-bottom: 2px solid var(--sc); }
.sec-h .n { font-family: var(--font-body); font-size: 13px; font-weight: 600; line-height: 1; color: var(--sc); background: var(--sc-soft); border-radius: 999px; padding: 5px 9px; }
.sec-h .all { margin-left: auto; font-family: var(--font-body); font-size: 14px; font-weight: 600; color: var(--sc); text-decoration: none; }
.sec-h .all:hover { text-decoration: underline; }

.cards { display: flex; flex-direction: column; gap: 18px; }
.card { position: relative; scroll-margin-top: 16px; background: var(--surface); border: 1px solid var(--line); border-left: 6px solid var(--sc, var(--tm)); border-radius: 10px; padding: 20px 22px 18px; }
.card .tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.card h3 { font-family: var(--font-display); font-weight: 600; font-size: 21px; line-height: 1.3; margin: 0 0 6px; text-wrap: balance; }
.card .facts { font-size: 13.5px; color: var(--muted); margin: 0 0 12px; }
.card .facts span + span::before { content: "·"; margin: 0 8px; }
.card p { margin: 0 0 10px; max-width: 78ch; }
.card .why { margin: 12px 0 0; padding: 10px 12px; background: var(--bg); border-radius: 6px; font-size: 14.5px; }
.card .why b { font-weight: 600; }
.card .basis { font-size: 13px; color: var(--muted); margin-top: 10px; }
.card .src-line { margin: -4px 0 14px; }
.card-foot { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 18px; margin-top: 12px; }
.card .src, .more .src { font-weight: 600; font-size: 14.5px; color: var(--sc, var(--tm)); text-decoration: none; border-bottom: 1.5px solid currentColor; padding-bottom: 1px; }
.card .src:hover, .card .src:focus-visible, .more .src:hover, .more .src:focus-visible { background: var(--sc-soft, var(--tm-soft)); }
.card .also { font-size: 13.5px; color: var(--muted); }
.card a.also, .card .also a { color: var(--muted); text-decoration: underline; text-underline-offset: 2px; }
.card a.also:hover, .card .also a:hover { color: var(--ink); }

.radar { margin-top: 32px; scroll-margin-top: 16px; }
.radar ul { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.radar li { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; font-size: 15px; }
.radar li .l1 { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 6px; }
.radar li > a.rl { color: var(--tm); font-weight: 600; text-decoration: none; border-bottom: 1px solid currentColor; }
.radar li .note { color: var(--muted); font-size: 13.5px; margin-top: 4px; }
.radar li .note a { color: inherit; }
.radar.compact { margin-top: 18px; }
.more { margin-top: 8px; }
.more summary { cursor: pointer; font-size: 14px; font-weight: 600; color: var(--muted); width: fit-content; }
.more summary:hover { color: var(--ink); }
.more summary:focus-visible { outline: 2px solid var(--tm); outline-offset: 2px; border-radius: 2px; }
.more-body { margin-top: 10px; padding-top: 12px; border-top: 1px dashed var(--line); }
.more-body p { margin: 0 0 10px; max-width: 78ch; }
.more-body .facts { font-size: 13.5px; color: var(--muted); }
.more-body .facts span + span::before { content: "·"; margin: 0 8px; }
.more-body .src-line { margin: -4px 0 12px; }
.more-body .why { padding: 10px 12px; background: var(--bg); border-radius: 6px; font-size: 14.5px; }
.more-body .why b { font-weight: 600; }
.more-body .basis { font-size: 13px; color: var(--muted); margin-bottom: 0; }
.radar.compact .section-title { font-size: 17px; }

.grp + .grp { margin-top: 34px; }
.grp-h { font-family: var(--font-display); font-size: 20px; font-weight: 600; margin: 22px 0 12px; }
.grp-h a { color: var(--ink); text-decoration: none; border-bottom: 1px solid var(--line); }
.grp-h a:hover { border-bottom-color: currentColor; }

.arch { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 14px; }
.arch > li { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px 20px; }
.arch h2 { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; font-family: var(--font-display); font-size: 21px; font-weight: 600; margin: 0; }
.arch h2 a { color: var(--ink); text-decoration: none; }
.arch h2 a:hover { color: var(--tm); }
.arch .m { margin: 2px 0 8px; font-size: 14px; color: var(--muted); }
.arch ul { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 4px; font-size: 15px; }
.arch ul a { color: var(--ink); text-decoration: none; border-bottom: 1px solid var(--line); }
.arch ul a:hover { color: var(--tm); border-bottom-color: var(--tm); }

footer.foot { margin-top: 34px; padding-top: 16px; border-top: 1px solid var(--line); font-size: 13px; color: var(--muted); }
footer.foot h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; margin: 0 0 6px; color: var(--ink); font-family: var(--font-body); font-weight: 600; }
footer.foot ul { margin: 0 0 12px; padding-left: 18px; }
footer.foot p { margin: 0 0 8px; }
footer.foot a { color: var(--ink); }
.site-foot { border-top: 1px solid var(--line); background: var(--surface); font-size: 14px; color: var(--muted); }
.site-foot .inner { padding-top: 18px; padding-bottom: 22px; }

@media (max-width: 480px) {
  .card { padding: 16px 16px 14px; }
  .card h3 { font-size: 19px; }
  .sec-h { font-size: 21px; }
  .sec-h .all { margin-left: 0; width: 100%; }
}
@media (prefers-reduced-motion: no-preference) {
  .card .src { transition: background .15s ease; }
}"""


IKONA_LUPA = ('<svg viewBox="0 0 20 20" width="17" height="17" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5" '
              'fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12.7 12.7 17 17" stroke="currentColor" '
              'stroke-width="1.8" stroke-linecap="round"/></svg>')

# Fulltextové hledání na stránce hledani.html. Data načítá z hledani.json (vytváří build.py),
# hledá bez ohledu na velikost písmen a diakritiku, všechna zadaná slova musí ve zprávě být.
SEARCH_JS = r"""<script>
(function () {
  var input = document.getElementById("hledat"), out = document.getElementById("vysledky"),
      info = document.getElementById("hledat-info"), data = null, timer;
  // Text bez diakritiky a malými písmeny; každý znak zůstává na svém místě kvůli zvýraznění.
  function norm(s) {
    var r = "";
    for (var i = 0; i < s.length; i++) {
      var c = s[i].normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
      r += c.length === 1 ? c : (c.charAt(0) || " ");
    }
    return r;
  }
  // Kmen slova kvůli skloňování (zlá víra → zl, vír: najde i „zlou víru“). Čísla a značky se nezkracují.
  function kmen(t) {
    if (/\d/.test(t) || t.length <= 2) return t;
    return t.length <= 5 ? t.slice(0, t.length - 1) : t.slice(0, t.length - 2);
  }
  function rx(k) {
    var e = k.replace(/[^a-z0-9]/g, function (c) { return "\\u" + ("000" + c.charCodeAt(0).toString(16)).slice(-4); });
    return new RegExp("(^|[^a-z0-9])" + e, "g");
  }
  function esc(s) {
    return s.replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  // Úseky textu, kde začíná některé hledané slovo; zvýrazní se celé slovo.
  function useky(n, re) {
    var res = [];
    re.forEach(function (r) {
      r.lastIndex = 0; var m;
      while ((m = r.exec(n)) !== null) {
        var a = m.index + m[1].length, b = a;
        while (b < n.length && /[a-z0-9]/.test(n[b])) b++;
        if (b === a) b = a + m[0].length - m[1].length;
        res.push([a, b]);
        r.lastIndex = Math.max(b, r.lastIndex);
      }
    });
    return res.sort(function (x, y) { return x[0] - y[0]; });
  }
  function mark(text, re) {
    var res = "", pos = 0;
    useky(norm(text), re).forEach(function (u) {
      if (u[0] < pos) return;
      res += esc(text.slice(pos, u[0])) + "<mark>" + esc(text.slice(u[0], u[1])) + "</mark>";
      pos = u[1];
    });
    return res + esc(text.slice(pos));
  }
  function snippet(text, re) {
    var u = useky(norm(text), re), i = u.length ? u[0][0] : -1;
    var start = 0, end = Math.min(text.length, 240);
    if (i > 90) { start = text.indexOf(" ", i - 90) + 1; end = Math.min(text.length, start + 240); }
    if (end < text.length) { var sp = text.lastIndexOf(" ", end); if (sp > start) end = sp; }
    return (start > 0 ? "… " : "") + mark(text.slice(start, end), re) + (end < text.length ? " …" : "");
  }
  function pocet(n) { return n + " " + (n === 1 ? "zpráva" : (n >= 2 && n <= 4 ? "zprávy" : "zpráv")); }
  function run() {
    var q = input.value.trim(), url = new URL(location.href);
    if (q) url.searchParams.set("q", q); else url.searchParams.delete("q");
    history.replaceState(null, "", url);
    if (!data) return;
    var re = norm(q).split(/\s+/).filter(function (t) { return t.length >= 2; }).map(function (t) { return rx(kmen(t)); });
    if (!re.length) {
      out.innerHTML = "";
      info.textContent = "Zadejte alespoň dvě písmena. Hledá se v hlavních zprávách i ve zprávách ve zkratce ze všech vydání (" + pocet(data.length) + ").";
      return;
    }
    var res = [];
    data.forEach(function (it) {
      var ht = norm(it.t), hx = norm(it.x + " " + it.s.join(" ") + " " + it.g.map(function (g) { return g[0]; }).join(" "));
      var score = 0;
      for (var i = 0; i < re.length; i++) {
        re[i].lastIndex = 0; var inT = re[i].test(ht);
        re[i].lastIndex = 0; if (!inT && !re[i].test(hx)) return;
        score += inT ? 3 : 1;
      }
      res.push({ it: it, score: score });
    });
    res.sort(function (a, b) { return b.score - a.score || (a.it.d < b.it.d ? 1 : a.it.d > b.it.d ? -1 : 0); });
    info.textContent = res.length ? "Nalezeno: " + pocet(res.length) : "Nic nenalezeno. Zkuste jiné nebo méně slov.";
    out.innerHTML = res.map(function (r) {
      var it = r.it;
      return '<li class="hit"><div class="hit-meta"><a href="archiv/' + it.d + '.html">' + esc(it.dl) + "</a> · " +
        esc(it.druh) + " · " + esc(it.s.join(", ")) + '</div><a class="hit-t" href="' + esc(it.u) + '">' + mark(it.t, re) +
        '</a><p class="hit-x">' + snippet(it.x, re) + '</p><div class="hit-tags">' +
        it.g.map(function (g) { return '<span class="pill ' + g[1] + '">' + esc(g[0]) + "</span>"; }).join("") + "</div></li>";
    }).join("");
  }
  var q0 = new URL(location.href).searchParams.get("q");
  if (q0) { input.value = q0; var nav = document.getElementById("q-nav"); if (nav) nav.value = q0; }
  input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 120); });
  fetch("hledani.json").then(function (r) { return r.json(); }).then(function (d) { data = d; run(); })
    .catch(function () { info.textContent = "Vyhledávání se nepodařilo načíst."; });
})();
</script>"""

# Přepínač světlého a tmavého režimu. Výchozí je světlý režim (data-theme="light" v <html>),
# tmavý se zapne přepínačem a prohlížeč si volbu zapamatuje.
THEME_HEAD = """<script>
try { var t = localStorage.getItem("ipnovinky-rezim"); if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t); } catch (e) {}
</script>"""

THEME_BODY = """<script>
(function () {
  var b = document.getElementById("theme-toggle");
  if (!b) return;
  var root = document.documentElement, mq = window.matchMedia("(prefers-color-scheme: dark)");
  function rezim() { return root.getAttribute("data-theme") || (mq.matches ? "dark" : "light"); }
  function sync() {
    var d = rezim() === "dark", text = d ? "Světlý režim" : "Tmavý režim";
    b.setAttribute("data-dark", d ? "true" : "false");
    b.setAttribute("aria-label", text);
    b.querySelector(".tt-label").textContent = text;
  }
  b.addEventListener("click", function () {
    var n = rezim() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", n);
    try { localStorage.setItem("ipnovinky-rezim", n); } catch (e) {}
    sync();
  });
  if (mq.addEventListener) mq.addEventListener("change", sync);
  sync();
})();
</script>"""

# Vstup heslem: dokud návštěvník nezadá heslo, vidí jen formulář. Správné heslo si
# prohlížeč zapamatuje (localStorage), takže se na dalších stránkách už neptá.
GATE_HEAD = """<script>
(function () {
  var k = "ipnovinky-pristup", t = "@HASH@";
  try { if (localStorage.getItem(k) === t || sessionStorage.getItem(k) === t) document.documentElement.classList.add("ok"); } catch (e) {}
})();
</script>"""

GATE_BODY = """<div class="gate">
  <form class="gate-box" id="gate-form" autocomplete="off">
    <p class="gate-msg">Obsah je přístupný jen s heslem.</p>
    <label class="sr" for="gate-pw">Heslo</label>
    <div class="gate-row">
      <input id="gate-pw" name="heslo" type="password" required autofocus>
      <button type="submit">Vstoupit</button>
    </div>
    <p class="gate-err" id="gate-err" role="alert" hidden>Nesprávné heslo, zkuste to znovu.</p>
    <noscript><p class="gate-err">Pro zobrazení stránky je potřeba povolit JavaScript.</p></noscript>
  </form>
  <p class="gate-contact">@KONTAKT@</p>
</div>
<script>
(function () {
  var k = "ipnovinky-pristup", t = "@HASH@";
  function h(s) {
    var x = 0x811c9dc5, b = new TextEncoder().encode("ipnovinky:" + s);
    for (var i = 0; i < b.length; i++) { x ^= b[i]; x = Math.imul(x, 0x01000193) >>> 0; }
    return ("0000000" + x.toString(16)).slice(-8);
  }
  var f = document.getElementById("gate-form"), pw = document.getElementById("gate-pw"), err = document.getElementById("gate-err");
  f.addEventListener("submit", function (e) {
    e.preventDefault();
    if (h(pw.value) !== t) { err.hidden = false; pw.select(); return; }
    try { localStorage.setItem(k, t); } catch (e1) { try { sessionStorage.setItem(k, t); } catch (e2) {} }
    document.documentElement.classList.add("ok");
    var a = location.hash && document.getElementById(location.hash.slice(1));
    if (a) a.scrollIntoView({ behavior: "instant", block: "start" }); else window.scrollTo({ top: 0, behavior: "instant" });
  });
})();
</script>"""

GATE_CSS = """html:not(.ok) body > :not(.gate) { display: none !important; }
html.ok .gate { display: none; }
.gate { min-height: 100vh; display: grid; grid-template-rows: 1fr auto 1fr; justify-items: center; padding: 24px 16px; }
.gate-box { grid-row: 2; width: 100%; max-width: 380px; background: var(--surface); border: 1px solid var(--line); border-top: 6px solid var(--navy); border-radius: 12px; padding: 24px 24px 22px; }
.gate .gate-msg { margin: 0 0 14px; font-size: 18px; font-weight: 600; color: var(--ink); }
.gate-contact { grid-row: 3; align-self: end; margin: 24px 0 0; font-size: 14px; color: var(--muted); }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.gate-row { display: flex; gap: 8px; }
.gate input { flex: 1; min-width: 0; font: inherit; font-size: 16px; color: var(--ink); background: var(--surface); border: 1px solid var(--muted); border-radius: 8px; padding: 10px 12px; }
.gate input:focus-visible, .gate button:focus-visible { outline: 2px solid var(--tm); outline-offset: 2px; }
.gate button { font: inherit; font-weight: 600; font-size: 16px; color: #fff; background: var(--navy); border: 0; border-radius: 8px; padding: 10px 18px; cursor: pointer; }
.gate button:hover { background: var(--tm); }
.gate .gate-err { margin: 12px 0 0; color: var(--comp); font-weight: 600; font-size: 14px; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .gate button { background: var(--tm); color: var(--bg); } }
:root[data-theme="dark"] .gate button { background: var(--tm); color: var(--bg); }"""


if __name__ == "__main__":
    sys.exit(main())
