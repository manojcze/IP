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

# Nenápadné upozornění nahoře na každé stránce.
AI_UPOZORNENI = ("AI generovaný výstup pro vlastní osobní potřebu. "
                 "Zákaz šíření a užívání pro jiné než edukativní účely.")


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
    return f"{n} {plural(n, 'zpráva', 'zprávy', 'zpráv')}"


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
    for t in st.get("oblasti", []) + st.get("jurisdikce", []) + st.get("soubeh", []):
        if t.strip().upper() == "NE" or "bez souběhu" in t.lower():
            chyby.append(f"{kde}: nepřípustný štítek „{t}“")


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
    ht = v.get("hlavni_temata", [])
    if len(ht) > 5:
        chyby.append(f"{name}: hlavních témat může být nejvýš 5")
    for t in ht:
        if t.get("zprava") not in ids:
            chyby.append(f"{name}: hlavní téma odkazuje na neexistující zprávu {t.get('zprava')}")
    radar = v.get("na_radar", [])
    if len(radar) > 3:
        chyby.append(f"{name}: položek Na radar může být nejvýš 3")
    for i, r in enumerate(radar):
        kde = f"{name}, Na radar {i + 1}"
        check_sekce(r.get("sekce"), kde, chyby)
        check_stitky(r.get("stitky"), kde, chyby)
        odkaz = r.get("odkaz") or {}
        if not str(odkaz.get("url", "")).startswith("http") or not odkaz.get("text"):
            chyby.append(f"{kde}: chybí odkaz (url a text)")
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

def pills(st):
    out = []
    for o in st.get("oblasti", []):
        cls = "tm" if o == "Ochranné známky" else "ip"
        out.append(f'<span class="pill {cls}">{o}</span>')
    out += [f'<span class="pill juris">{j}</span>' for j in st.get("jurisdikce", [])]
    out += [f'<span class="pill comp-yes">{s}</span>' for s in st.get("soubeh", [])]
    if st.get("starsi"):
        out.append('<span class="pill old">Starší zpráva</span>')
    return "".join(out)


def issue_meta(v):
    n, r = len(v["zpravy"]), len(v["na_radar"])
    s = pocet_zprav(n)
    if r:
        s += f" + {r} na radar"
    return s


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
    return f"""    <article class="card s-{hlavni}" id="{cid}">
      <div class="tags">{pills(z["stitky"])}</div>
      <h3>{z["nadpis"]}</h3>
      <p class="facts">{fakta}</p>
      <p class="src-line">{zdroj}</p>
      {odst}
      <p class="why"><b>{oznaceni}</b> {dopad["text"]}</p>
      <p class="basis">{z["podklad"]}</p>{foot}
    </article>"""


def radar_item(r, root, v=None):
    poznamka = f'<div class="note">{r["poznamka"]}</div>' if r.get("poznamka") else ""
    text = f': {r["text"]}' if r.get("text") else ""
    odkud = ""
    if v is not None:
        odkud = f'<div class="note"><a href="{root}archiv/{v["datum"]}.html#na-radar">Z vydání {d_short(v["_d"])}</a></div>'
    return f"""      <li>
        <div class="l1">{pills(r["stitky"])}</div>
        <a href="{url_attr(r["odkaz"]["url"])}">{r["odkaz"]["text"]}</a>{text}
        {poznamka}{odkud}
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
                    f'<span class="m">{pocet_zprav(len(v["zpravy"]))}{tag}</span></a></li>')
    rows.append("</ol>")
    legenda = ('<span class="pill tm">Ochranné známky</span>'
               '<span class="pill ip">Jiná oblast IP</span>'
               '<span class="pill juris">Jurisdikce</span>'
               '<span class="pill comp-yes">Souběh se soutěžním právem / s nekalou soutěží</span>'
               '<span class="pill old">Starší zpráva</span>')
    return f"""<aside class="side" aria-label="Seznam vydání">
  <div class="side-inner">
    <section class="panel issues">
      <h2>Všechna vydání</h2>
      {chr(10).join(rows)}
      <p class="arch-link"><a href="{root}archiv/">Přehled vydání s obsahem →</a></p>
    </section>
    <section class="panel legend">
      <h2>Štítky</h2>
      <div class="pills">{legenda}</div>
    </section>
  </div>
</aside>"""


def page(*, title, root, brand, h1, meta, nav_current, content, side=None, description=""):
    nav = [("index", f"{root}./" if root else "./", "Aktuální vydání", "")]
    nav += [(slug, f"{root}sekce/{slug}.html", nazev, f" s-{slug}") for slug, nazev in SEKCE]
    nav.append(("archiv", f"{root}archiv/", "Všechna vydání", ""))
    cur = ' aria-current="page"'
    nav_html = "\n".join(
        f'      <li><a class="nl{cls}" href="{href}"{cur if key == nav_current else ""}>{label}</a></li>'
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
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>{desc}{head_gate}
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
    <div class="brand"><a href="{root}./">{brand}</a></div>
    <h1>{h1}</h1>{f'{chr(10)}    <div class="meta-row">{meta}</div>' if meta else ""}
  </div>
</header>

<nav class="sections" aria-label="Sekce">
  <div class="inner">
    <ul>
{nav_html}
    </ul>
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
        items = "\n".join(radar_item(r, root) for r in v["na_radar"])
        parts.append(f"""  <section class="radar" id="na-radar" aria-labelledby="radar-h">
    <h2 class="section-title" id="radar-h">Na radar</h2>
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
    return page(title=f"IP novinky {d_short(d)}", root=root,
                brand="Přehled dvakrát týdně · duševní vlastnictví", h1="IP novinky",
                meta="", nav_current=nav_current, content="\n\n".join(parts),
                side=sidebar(vydani, root, v), description=hlavni)


def section_page(slug, nazev, vydani):
    root = "../"
    seen = {}       # klic -> vydání, ve kterých se zpráva opakovala
    groups, n_z, n_r, n_v = [], 0, 0, 0
    # Starší výskyty stejné věci (pole klic) se nezobrazí, jen se uvedou u nejnovější verze.
    for v in vydani:
        for z in v["zpravy"]:
            if z.get("klic"):
                seen.setdefault(z["klic"], []).append(v)
    shown = set()
    for v in vydani:
        zz = []
        for z in v["zpravy"]:
            if slug not in z["sekce"]:
                continue
            k = z.get("klic")
            if k and k in shown:
                continue
            if k:
                shown.add(k)
            also = [x for x in seen.get(k, []) if x is not v] if k else None
            zz.append(card(z, v, root, "sekce", also_in=also))
        rr = [radar_item(r, root) for r in v["na_radar"] if slug in r["sekce"]]
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
            blok.append('    <div class="radar compact"><h3 class="section-title">Na radar</h3><ul>\n'
                        + "\n".join(rr) + "\n    </ul></div>")
        blok.append("  </section>")
        groups.append("\n".join(blok))
    if groups:
        content = "\n\n".join(groups)
    else:
        content = ('  <p class="empty">V této sekci zatím není žádná zpráva. '
                   'Jakmile se v některém vydání objeví, najdete ji tady.</p>')
    content = (f'  <p class="lead">Zprávy ze všech vydání zařazené do sekce {nazev}, od nejnovějších.</p>\n\n'
               + content + f'\n\n  <footer class="foot">\n    <h2>Upozornění</h2>\n    <p>{UPOZORNENI}</p>\n  </footer>')
    if n_z or n_r:
        meta = f"<span><strong>{pocet_zprav(n_z)}</strong></span>"
        if n_r:
            meta += f"<span>{n_r} na radar</span>"
        meta += f"<span>z {n_v} {plural(n_v, 'vydání', 'vydání', 'vydání')}</span>"
    else:
        meta = "<span>Zatím bez zpráv</span>"
    return page(title=f"{nazev} – IP novinky", root=root, brand="IP novinky · sekce", h1=nazev,
                meta=meta, nav_current=slug, content=content, side=sidebar(vydani, root),
                description=f"Přehled novinek z oblasti {nazev.lower()} ze všech vydání IP novinek.")


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
    return page(title="Všechna vydání – IP novinky", root=root, brand="IP novinky",
                h1="Všechna vydání", meta=f"<span>{n} {plural(n, 'vydání', 'vydání', 'vydání')}</span>",
                nav_current="archiv", content=content, description="Archiv všech vydání IP novinek.")


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
.brand { font-size: 13px; letter-spacing: .08em; text-transform: uppercase; color: #9fb4da; font-weight: 600; }
.brand a { color: inherit; text-decoration: none; }
.brand a:hover { color: #fff; }
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
nav.sections ul { list-style: none; margin: 0; padding: 0; display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; }
nav.sections ul::-webkit-scrollbar { display: none; }
nav.sections li:first-child a { padding-left: 0; }
nav.sections a { display: block; padding: 13px 12px 10px; font-weight: 600; font-size: 15px; color: var(--muted); text-decoration: none; border-bottom: 3px solid transparent; white-space: nowrap; }
nav.sections a:hover { color: var(--ink); }
nav.sections a[aria-current="page"] { color: var(--ink); border-bottom-color: var(--sc, var(--ink)); }

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
.issues ol a { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; padding: 7px 10px; margin: 0 -10px; border-radius: 6px; text-decoration: none; color: var(--ink); }
.issues ol a:hover { background: var(--bg); }
.issues ol a[aria-current="page"] { background: var(--tm-soft); color: var(--tm); }
.issues .d { font-weight: 600; font-variant-numeric: tabular-nums; }
.issues .m { font-size: 13px; color: var(--muted); white-space: nowrap; }
.issues .arch-link { margin: 10px 0 0; padding-top: 10px; border-top: 1px solid var(--line); font-size: 14px; }
.issues .arch-link a { color: var(--tm); font-weight: 600; text-decoration: none; }
.legend .pills { display: flex; flex-wrap: wrap; gap: 6px; }
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
.card .src { font-weight: 600; font-size: 14.5px; color: var(--sc, var(--tm)); text-decoration: none; border-bottom: 1.5px solid currentColor; padding-bottom: 1px; }
.card .src:hover, .card .src:focus-visible { background: var(--sc-soft, var(--tm-soft)); }
.card .also { font-size: 13.5px; color: var(--muted); }
.card a.also, .card .also a { color: var(--muted); text-decoration: underline; text-underline-offset: 2px; }
.card a.also:hover, .card .also a:hover { color: var(--ink); }

.radar { margin-top: 32px; scroll-margin-top: 16px; }
.radar ul { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.radar li { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; font-size: 15px; }
.radar li .l1 { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 6px; }
.radar li > a { color: var(--tm); font-weight: 600; text-decoration: none; border-bottom: 1px solid currentColor; }
.radar li .note { color: var(--muted); font-size: 13.5px; margin-top: 4px; }
.radar li .note a { color: inherit; }
.radar.compact { margin-top: 18px; }
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
