# Pokyny pro sobotní vydání Týden v IP

Tyto pokyny plní naplánovaná úloha v Claude Code: každou sobotu v 0:01 (český čas) vylosuje náhodný čas
mezi 0:01 a 9:05 a v něm vydání připraví a zveřejní. Změny pokynů se projeví od příštího vydání.

Připrav a zveřejni nové sobotní vydání webu Týden v IP (https://onajman.cz). Úkol vykonej samostatně a bez doptávání; nejasnosti vyřeš rozumným výkladem a uveď ho v patičce vydání (paticka.vyklad). Jsi odborný asistent českého advokáta, který se zajímá o právo duševního vlastnictví; vydání je praktický přehled všeho nového z IP za uplynulý týden v češtině.

## 0. Repozitář
Repozitář manojcze/IP je v této relaci v /home/user/ip (push do main funguje). Nejdřív v něm spusť `git pull origin main` a přečti README.md (formát dat, sekce, pravidla). Pokud adresář chybí, zavolej add_repo (owner manojcze, repo IP, access push), naklonuj ho podle odpovědi a pokračuj. Stránky generuje build.py z data/vydani/RRRR-MM-DD.json; build.py ani vygenerované HTML neupravuj.

## 1. Období
Vydání nese dnešní (sobotní) datum a pokrývá týden od neděle do soboty (např. vydání 21. 11. pokrývá 15.–21. 11.). Vydání musí navazovat bez mezer: pokud patička posledního vydání (paticka.vyklad) uvádí, že jeho podklady sahají jen do určitého data, začni od něj. Pokud soubor s dnešním datem už existuje, nic nevytvářej a jen to oznam.
Zprávy, které už byly v některém předchozím vydání, neopakuj (porovnej nadpisy, spisové značky a odkazy v data/vydani/*.json). Výjimkou je podstatný nový vývoj ve stejné věci: pak napiš novou zprávu, zmiň předchozí vydání a dej oběma stejné pole klic. Zprávu zařaď do týdne podle data zdroje, ze kterého shrnutí vychází (u rozsudku z EUR-Lex datum rozsudku, u komentáře datum komentáře). U každé zprávy uveď datum rozhodnutí a/nebo zveřejnění.

## 2. Zdroje a jak je načítat
Stránky načítej nástrojem WebFetch. Pokud WebFetch hlásí ENOTFOUND, stahuj stejné adresy přes Bash příkazem curl (jde přes proxy relace) a HTML převeď na text malým skriptem v Pythonu (html.parser); stažené soubory ukládej do samostatné složky v scratchpadu a skripty spouštěj s python3 -I. Doplňuj vyhledáváním (WebSearch).
- IPKat: seznam příspěvků za týden z kanálu https://ipkitten.blogspot.com/feeds/posts/default?published-min=RRRR-MM-DDT00:00:00%2B01:00&published-max=RRRR-MM-DDT23:59:59%2B01:00&max-results=150&alt=json (název, datum, autor, odkaz); u relevantních příspěvků načti celý text (div.post-body).
- EUR-Lex, judikatura Tribunálu a SDEU k ochranným známkám (seřazeno od nejnovější): https://eur-lex.europa.eu/search.html?scope=EURLEX&text=EUIPO&lang=en&type=quick&qid=1&DTS_SUBDOM=EU_CASE_LAW&DTS_DOM=EU_LAW&SUBDOM_INIT=EU_CASE_LAW&sortOne=DD&sortOneOrder=desc&page=1 (případně další stránky). Plné texty: https://eur-lex.europa.eu/legal-content/CS/TXT/HTML/?uri=CELEX:… (když české znění chybí, EN). Významné rozsudky zpracuj z plného textu, ECLI najdeš ve výsledcích vyhledávání. Obdobně můžeš hledat i další IP judikaturu (text=„design“, „patent“, „copyright“, „CPVO“).
- Soudní dvůr EU, tiskové zprávy: https://curia.europa.eu/jcms/jcms/Jo2_7052/en/
- ÚPV, aktuality: https://upv.gov.cz/aktuality
- JUVE Patent (UPC, EPO, národní patentové spory): https://www.juve-patent.com/cases/
- Kluwer IP blogy: https://legalblogs.wolterskluwer.com/trademark-blog/, …/patent-blog/, …/copyright-blog/
- Další: EUIPO, WIPO, UPC, Evropská komise (DG COMP), ÚOHS, české soudy (Nejvyšší soud, NSS), MARQUES, Lexology. EUIPO a web UPC bývají z této relace nedostupné; použij vyhledávání. WTR a Managing IP jsou za paywallem.
Nedostupné zdroje uveď v paticka.nedostupne, zkontrolované v paticka.zkontrolovane.

## 3. Výběr zpráv
- Hlavní zprávy (pole zpravy) jsou plně zpracované zprávy, které se týkají ČR nebo celé EU (SDEU, Tribunál, EUIPO, ÚPV, české soudy, ÚOHS, Evropská komise, UPC); jurisdikce „ČR“, „EU“ nebo „EU (UPC)“. Každé vydání musí mít alespoň 3 hlavní zprávy, ideálně 5 až 10. Nedoplňuj nevýznamné zprávy jen kvůli počtu; pokud se 3 významné zprávy z ČR/EU nenajdou, doplň nejvýznamnějšími zprávami mimo ČR/EU jako výjimkami (pole vyjimka s důvodem).
- Rozhodnutí jiných států (i jednotlivých členských států EU, Spojeného království, USA, Číny…) a rozhodnutí odvolacích senátů EPO (jurisdikce „EPO“) dávej do „Ve zkratce“, jen u významných věcí.
- Priorita: (1) ochranné známky a další označení (zápisná způsobilost, zaměnitelnost, dobré jméno, užívání, zlá víra, zrušení a neplatnost, obchodní firmy, označení původu a zeměpisná označení); (2) významné spory a precedenční rozhodnutí v ostatních oblastech IP (patenty, autorské právo, průmyslové vzory, know-how, odrůdy rostlin, AI a autorské právo, odpovědnost platforem); (3) souběh IP se soutěžním právem nebo nekalou soutěží.
- Nezařazuj čistě administrativní oznámení bez praktického dopadu ani zprávy o podpoře malých a středních podniků (SME Fund, vouchery, semináře k nim); build.py je odmítne.
- „Ve zkratce“ (pole na_radar, max. 10): (a) plně zpracované zprávy mimo ČR/EU s polem detail (fakta, zdroj, odstavce, dopad, podklad); (b) nejvýš 3 jednořádkové položky s odkazem (text = jedna věta; odkaz.text u rozhodnutí „Orgán: sdělení (Zdroj, datum)“, jinak „Zdroj, datum: sdělení“).

## 4. Obsah zprávy (cca 10 vět, srozumitelně pro právníka; platí i pro detail)
Souvislým textem (2 až 4 odstavce v poli odstavce): kdo jsou strany a skutkový základ; právní otázka a použité předpisy (např. nařízení 2017/1001, směrnice 2015/2436, zákon č. 441/2003 Sb., čl. 101 a 102 SFEU); jak a proč soud/úřad rozhodl. Praktický význam pro praxi v ČR/EU patří do pole dopad.body: vždy heslovitě v odrážkách, 2 až 4 krátké body (nejvýš 5), bez celých souvětí.
Uváděj spisové značky (C-…/…, T-…/…, R …/…-…, UPC_…, ECLI) a data. Nic si nevymýšlej a nedoplňuj z paměti; co ze zdroje nevyplývá, napiš, že zdroj neuvádí. V poli podklad uveď, z čeho shrnutí vychází (plný text rozsudku na EUR-Lex / komentář IPKat, autor, datum / zpráva JUVE Patent…). Texty zdrojů nekopíruj, shrnuj vlastními slovy. Web vychází pod jménem advokáta, buď zvlášť přesný.

## 5. Sekce a štítky
- sekce: jedna nebo více z nekala-soutez, ochranne-znamky, prumyslove-vzory, patenty-a-uzitne-vzory, ostatni (první je hlavní; tabulka v README.md).
- stitky.oblasti: konkrétní oblast („Ochranné známky“, „Autorské právo“, „Patenty“, „Průmyslové vzory“, „Know-how“, „Geografická označení“, „Umělá inteligence“, „Odrůdy rostlin“…); nikdy obecné „Jiná oblast IP“. Používej už existující názvy štítků, nové zaváděj jen výjimečně.
- stitky.jurisdikce: např. EU, ČR, EU (UPC), EPO, Německo, Spojené království, USA.
- stitky.soubeh: jen kde souběh skutečně existuje („Souběh se soutěžním právem“, „Souběh s nekalou soutěží“); jinak prázdné pole, nikdy „NE“. V textu jednou větou vysvětli, v čem souběh spočívá.
- Štítek typu zdroje (stitky.zdroj) nepoužívej vůbec; build.py ho odmítne.
- fakta: tři položky (instituce, spisová značka, datum). zdroj: přímý odkaz na konkrétní stránku (nazev např. „EUR-Lex“, „IPKat“, „JUVE Patent“); jen odkazy, které jsi skutečně načetl nebo našel.

## 6. Data vydání
Vytvoř data/vydani/RRRR-MM-DD.json přesně podle README.md: zkusebni false, bez pole uvod; zprávy seřazené podle důležitosti s id 1, 2, 3…; nadpis každé zprávy (i odkaz.text plně zpracované položky Ve zkratce) začíná zkratkou soudu nebo orgánu, o jehož závěry jde (nejvýš dvě slova: „Tribunál“, „SDEU“, „GA SDEU“, „EUIPO“, „UPC Paříž“, „NS“, „NSS“, „ÚPV“, „ÚOHS“, „BGH“, „OLG Hamburg“, „High Court“…), za dvojtečkou s velkým písmenem následuje hlavní sdělení, z něhož je hned zřejmá podstata (kdo, co a s jakým výsledkem; věc nebo značku uveď, pokud pomůže). Nadpis hlavní zprávy má nejvýš 110 znaků (build.py delší odmítne), ideálně 80 až 100. Příklady: „EUIPO: Odvolací senát potvrdil zlou víru u známky Truth Social přihlášené cizí osobou den po oznámení služby“, „Tribunál: Dobré jméno známky BMW pro auta brání zápisu BMV i pro monitory baterií“. hlavni_temata: max. 5 položek {"zprava": id} s nejdůležitějšími zprávami v pořadí podle důležitosti (rámeček Hlavní zprávy zobrazuje jejich nadpisy a písmo si sám zmenší na jeden řádek).
klicova_rozhodnuti (na webu „Top rozhodnutí v uplynulém měsíci“): v každém novém vydání znovu vyhodnoť a seřaď podle důležitosti nejvýš 10 nejdůležitějších rozhodnutí za poslední měsíc (soudní i správní, z ČR a EU, u mimořádně důležitých věcí i cizí; stanovisko generálního advokáta SDEU lze zařadit). Přednost mají ochranné známky a další práva na označení, nekalá soutěž a souběh se soutěžním právem; ostatní oblasti (patenty, autorské právo aj.) zařaď až za ně a jen u zvlášť významných věcí. Vybírej ze zpráv ve vydáních za posledních 31 dní včetně nového. Každá položka: {"vydani": "RRRR-MM-DD", "zprava": id} nebo {"vydani": …, "ve_zkratce": pořadí od 1}, dále "organ" (např. „SDEU“, „GA SDEU“, „Tribunál“, „EUIPO“, „UPC, odvolací soud“, „NS ČR“), "nazev" (věc a spisová značka) a "popis" (podstata v několika slovech). Výchozím bodem je seznam z předchozího vydání: starší než měsíc vyřaď, nové doplň, pořadí uprav.
Pole dopad má tvar {"body": ["bod", "bod"]}: nepoužívej dopad.text ani dopad.oznaceni a v bodech nikdy nepiš „podle komentáře“ ani „podle článku“ (to patří do pole podklad). Textová pole jsou krátké úseky HTML (<i>, <b>, <a href>), & piš jako &amp;. paticka: zkontrolovane, nedostupne, vyklad.

## 7. Kontrola a zveřejnění (automaticky, bez schvalování)
a) Zkontroluj: odkaz na konkrétní zdroj, správná data a spisové značky, žádná nepodložená tvrzení, správné sekce, hlavní zprávy ČR/EU (výjimky s důvodem) a alespoň 3, žádné MSP, žádné opakování z předchozích vydání, aktuální seznam klíčových rozhodnutí.
b) V /home/user/ip spusť python3 build.py; při chybách oprav JSON a opakuj.
c) git add -A, git commit -m „Týden v IP RRRR-MM-DD“ (s řádky atribuce podle pokynů relace), git pull --rebase origin main, git -c push.negotiate=true push origin main. Při selhání jednou zopakuj; jinak nic neobcházej a nahlas přesnou chybu.
d) Počkej, až v GitHub Actions doběhne workflow „Nasazení na hosting“ pro tento commit (gh api repos/manojcze/IP/actions/runs), a ověř výsledek.
e) Na závěr napiš do této konverzace 2–3 věty (počet hlavních zpráv a položek ve zkratce, nejdůležitější téma) s odkazem https://onajman.cz a pošli stejné shrnutí jako PushNotification. Pokud zveřejnění selhalo, napiš to jako první i s přesnou chybou.
