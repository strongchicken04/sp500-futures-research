"""Build the final ranked report (Czech) from results/lab/metrics.json."""
import json, os, sys

DESC = {
 "01_orb5_10r": dict(
   nazev="ORB 5 min (10R cíl)",
   rodina="trend / breakout",
   params="opening range = první 5min svíčka (9:30–9:35); směr dle té svíčky; stop na opačném extrému OR; cíl 10R; jinak exit 16:00; 1 obchod/den",
   popis="Klasický Opening Range Breakout z paperu Zarattini & Aziz (SSRN 4416622). Vsadí na to, že směr prvních 5 minut udává směr dne.",
   proc="Ranní otevření nese největší informační tok (přes noc nasbírané zprávy). Průraz počátečního rozpětí značí, že jedna strana převládla."),
 "02_orb15_3r": dict(
   nazev="ORB 15 min (3R cíl)",
   rodina="trend / breakout",
   params="opening range = 9:30–9:45; stop opačný extrém; cíl 3R; exit 16:00; 1 obchod/den",
   popis="Pomalejší varianta ORB — širší rozpětí, méně falešných průrazů, ale horší poměr risk/reward.",
   proc="Delší okno filtruje ranní šum, ale zároveň zdražuje stop (širší OR = větší R)."),
 "03_orb30_eod": dict(
   nazev="ORB 30 min (bez cíle, exit EOD)",
   rodina="trend / breakout",
   params="opening range = 9:30–10:00; stop opačný extrém; žádný TP; exit 16:00; 1 obchod/den",
   popis="Nejpomalejší ORB — nechává vítěze běžet celý den.",
   proc="Kombinuje filtraci šumu (30 min) s trend-following exitem (nechat běžet)."),
 "04_vwap_band": dict(
   nazev="VWAP hysterezní pásmo (20 bps)",
   rodina="trend / breakout",
   params="session VWAP (HLC3); vstup když 1min close zavře za VWAP ±20 bps; exit close za opačným pásmem nebo 16:00; 1 obchod/den",
   popis="Jádro strategie Strong Chicken VWAP Trend. Hystereze (mrtvé pásmo) filtruje whipsawy kolem VWAP.",
   proc="VWAP je vnitrodenní rovnovážná cena. Trvalý odklon = nerovnováha v order flow; pásmo brání reagovat na šum."),
 "05_vwap_band_gates": dict(
   nazev="VWAP pásmo + gap gate + trend gate",
   rodina="trend / breakout",
   params="jako #04, navíc: neobchoduj když |overnight gap| < 25. percentil 250 dní, nebo když včerejší trendovost > 60. percentil",
   popis="Finální konfigurace VWAP Trend z tvého výzkumu. Brány vynechají dny bez ranní energie a dny po vyčerpávajícím trendu.",
   proc="Trend-following potřebuje pohyb. Malý gap = den bez katalyzátoru; po silně trendovém dni přichází konsolidace."),
 "06_pdh_pdl_break": dict(
   nazev="Průraz včerejšího high/low",
   rodina="trend / breakout",
   params="vstup při průrazu předchozího denního maxima/minima; stop 0,5×ATR(14); exit 16:00",
   popis="Nejstarší breakout myšlenka vůbec — obchoduj průraz úrovně, kterou sleduje celý trh.",
   proc="PDH/PDL jsou referenční body s nakupenými stop příkazy; jejich průraz spouští kaskádu."),
 "07_donchian20": dict(
   nazev="Donchian kanál 20 (5min)",
   rodina="trend / breakout",
   params="5min bary; long při close nad 20-barovým maximem, short pod minimem; exit při 10-barovém protisměrném extrému nebo 16:00",
   popis="Vnitrodenní verze klasického Turtle systému.",
   proc="Nová N-barová extrémní hodnota = pokračování trendu. Funguje na denní úrovni už 40 let."),
 "08_intraday_momentum": dict(
   nazev="Intradenní momentum (noise band)",
   rodina="trend / breakout",
   params="pásmo = 14denní průměr |close−open| kolem dnešního openu; průraz nahoru = long, dolů = short; exit EOD",
   popis="Zjednodušená replikace Zarattini 'Beat the Market' (SSRN 4824172) — obchoduje abnormální vychýlení proti běžnému dennímu rozsahu.",
   proc="Když se cena vzdálí od openu víc, než je pro daný trh běžné, jde o skutečnou nerovnováhu, ne šum."),
 "09_first_hour_break": dict(
   nazev="Průraz rozpětí první hodiny",
   rodina="trend / breakout",
   params="rozpětí 9:30–10:30; průraz = vstup; stop na opačné straně rozpětí; exit 16:00",
   popis="ORB s hodinovým oknem — nejrozšířenější retailová varianta.",
   proc="První hodina absorbuje overnight nerovnováhu; co se stane potom, je 'skutečný' směr dne."),
 "10_ema_cross": dict(
   nazev="EMA 9/21 kříž (5min)",
   rodina="trend / breakout",
   params="5min bary; křížení EMA9 nad/pod EMA21 = vstup; opačný kříž nebo 16:00 = exit",
   popis="Nejznámější indikátorová strategie na světě. Kontrolní vzorek: funguje vůbec ještě klouzavý průměr intradenně?",
   proc="Kříž rychlého a pomalého průměru má detekovat změnu režimu. Na vnitrodenních datech je ale zpožděný."),
 "11_vwap_reversion": dict(
   nazev="VWAP reverze (fade extrému)",
   rodina="mean reversion",
   params="z-skóre = (cena−VWAP)/σ(30 barů); |z|>2 = vstup proti pohybu; cíl VWAP; stop 1,5σ; exit 16:00",
   popis="Přesně ten model, který popisuje paper Lee (SSRN 6438039) — jen doplněný o obchodní pravidla, která paper neuvádí.",
   proc="Cena se má vracet k volume-váženému průměru; extrémní odklon = přestřelení, které se opraví."),
 "12_bollinger_fade": dict(
   nazev="Bollinger fade (5min, 20/2)",
   rodina="mean reversion",
   params="5min bary; close nad horním pásmem = short, pod dolním = long; cíl střední pásmo; exit 16:00",
   popis="Učebnicová mean-reversion strategie z každé knihy o technické analýze.",
   proc="Cena se pohybuje ve statistickém kanálu; dotyk okraje = přestřelení a návrat ke střední hodnotě."),
 "13_rsi2": dict(
   nazev="RSI(2) vnitrodenní reverze",
   rodina="mean reversion",
   params="5min bary; RSI(2) < 5 = long, > 95 = short; exit při návratu RSI přes 55/45 nebo 16:00",
   popis="Larry Connors RSI(2) — na denních datech legendárně funkční systém, testovaný zde intradenně.",
   proc="Krátkodobě extrémně přeprodaný/překoupený stav se rychle koriguje."),
 "14_gap_fade": dict(
   nazev="Fade otevíracího gapu",
   rodina="mean reversion",
   params="pouze dny s |gap| > 20 bps; vstup proti gapu na openu; cíl = zaplnění gapu (včerejší close); stop 40 bps; exit 16:00",
   popis="Klasika: 'gapy se zaplňují'. Obchoduje proti nočnímu pohybu.",
   proc="Overnight pohyb bez objemu často přestřelí; RTH likvidita ho koriguje zpět."),
 "15_late_reversal": dict(
   nazev="Odpolední reverze",
   rodina="mean reversion",
   params="ve 14:30 změř pohyb dne (close/open−1); pokud |pohyb| > 40 bps, vstup proti němu; exit 16:00",
   popis="Sázka na to, že vyhrocený denní pohyb se ke konci dne částečně vrací.",
   proc="Intradenní trend vyčerpá kupce/prodejce; závěrečné vyrovnávání pozic tlačí cenu zpět."),
 "16_overnight": dict(
   nazev="Overnight hold (close → open)",
   rodina="časová / sezónní",
   params="nákup na close v 16:00, prodej na openu v 9:30 následujícího dne; každý den; žádný stop",
   popis="Slavná akademická anomálie: většina výnosu akciových indexů vzniká přes noc, ne během dne.",
   proc="Riziková prémie za držení přes noc (nelze reagovat na zprávy) + systematické nakupování při otevření."),
 "17_power_hour": dict(
   nazev="Power hour momentum (15:00→16:00)",
   rodina="časová / sezónní",
   params="v 15:00: pokud cena nad VWAP → long, pod VWAP → short; exit na close 16:00",
   popis="Obchoduje poslední hodinu, kdy je největší objem a doznívá denní směr.",
   proc="Závěrečná aukce a rebalancování fondů posiluje převládající denní směr."),
 "18_lunch_fade": dict(
   nazev="Polední fade (12:00→14:00)",
   rodina="časová / sezónní",
   params="ve 12:00 vstup proti rannímu pohybu (pokud |pohyb| > 30 bps); exit ve 14:00",
   popis="Obchoduje nejklidnější část dne, kdy podle folklóru trh koriguje ranní přehnanou reakci.",
   proc="Nízká polední likvidita = mean-reverting režim; institucionální flow se pauzuje."),
 "19_ema_vwap_wick": dict(
   nazev="EMA9 + VWAP knot (Instagram)",
   rodina="instagram (kontrolní vzorek)",
   params="3min bary; vstup když svíčka knotem probodne VWAP a zavře zpět; exit když svíčka zavře za EMA9; bez stopu",
   popis="Strategie z instagramového videa ('best strategy I've ever used').",
   proc="Odraz od VWAP jako vstup + EMA jako trailing exit. Ve skutečnosti jde o trend-following v přestrojení."),
 "20_no_wick": dict(
   nazev="No Wick (Instagram)",
   rodina="instagram (kontrolní vzorek)",
   params="1min; bezknotová svíčka ve směru trendu (EMA50) → označ úroveň; vstup při návratu ceny na úroveň (do 8 svíček); stop poslední swing; TP 1:1",
   popis="Strategie z instagramového videa ('founded it 2.5 years ago, everyone becomes profitable').",
   proc="Bezknotová svíčka má značit institucionální absorpci; návrat na úroveň = vstupní příležitost."),
}

def fmt(v, dec=2, suf=""):
    try: return f"{float(v):.{dec}f}{suf}"
    except Exception: return str(v)

def main(metrics_path, out_md, imgdir="lab"):
    with open(metrics_path) as f: M = json.load(f)
    # rank: primary Sharpe, require positive CAGR to be "viable"
    rank = sorted(M.items(), key=lambda kv: (-kv[1]["sharpe"], -kv[1]["cagr"]))
    L = []
    L.append("# Velký test 20 vnitrodenních strategií — NQ (NAS100 proxy)\n")
    L.append("*Projekt Strong Chicken • 1-min data • **IS 2005–2017 (13 let)** • OOS 2018–2020/05 schováno*\n")
    L.append("## Metodika\n")
    L.append("- **Data:** OANDA NAS100 1-min (proxy na NQ), regular trading hours 9:30–16:00 ET, 2005–2017 = **3 270 obchodních dní**.\n"
             "- **Náklady:** **1 bps za stranu** (2 bps round-trip) — konzervativní pro index futures, aplikováno na každý obchod.\n"
             "- **Sizing:** 1 jednotka nominálu na obchod (bez páky). Denní výnos = součet výnosů obchodů toho dne; equity se skládá denně. Díky tomu jsou strategie s různou frekvencí **přímo porovnatelné**.\n"
             "- **Řazení:** primárně podle **Sharpe ratio** (výnos na jednotku kolísání) — ne podle výnosu, protože ten jde vždy nafouknout pákou.\n"
             "- **Monte Carlo:** 500 bootstrapových cest po 250 obchodních dní (fan chart) + 400 scénářů výnos×drawdown (oblak).\n"
             "- **OOS:** roky 2018 – 2020/05 nebyly použity a zůstávají čisté pro finální ověření vybrané strategie.\n")
    L.append("\n## Žebříček (od nejlepší po nejhorší)\n")
    L.append("| # | strategie | rodina | Sharpe | CAGR | MaxDD | Calmar | PF | win% | obchodů | MC kladných |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for i,(k,v) in enumerate(rank,1):
        d=DESC.get(k,{})
        L.append(f"| {i} | **{d.get('nazev',k)}** | {d.get('rodina','')} | **{fmt(v['sharpe'])}** | {fmt(v['cagr'],1,' %')} | "
                 f"{fmt(v['mdd'],1,' %')} | {fmt(v.get('calmar',0))} | {fmt(v['pf'])} | {fmt(v['win'],0,' %')} | "
                 f"{v['n']} | {fmt(v.get('mc_positive_pct',0),0,' %')} |")
    try:
        B=json.load(open(os.path.join(os.path.dirname(metrics_path),"benchmark.json")))
        L.append(f"| — | *Benchmark: prosté držení NAS100* | benchmark | *{B['sharpe']:.2f}* | *{B['cagr']:.1f} %* | *{B['mdd']:.1f} %* | *{B['cagr']/abs(B['mdd']):.2f}* | — | — | — | — |")
    except Exception: B=None
    L.append("\n> **Jak číst tabulku:** Sharpe > 1 je slušné, > 1,5 velmi dobré. Calmar = CAGR ÷ |MaxDD| (kolik výnosu na jednotku bolesti). "
             "PF (profit factor) > 1 = strategie vydělává; < 1 = prodělává. „MC kladných“ = kolik procent Monte Carlo scénářů skončilo v zisku.\n")

    pos=[k for k,v in M.items() if v["cagr"]>0]
    L.append("\n## Hlavní zjištění\n")
    L.append(f"**1. Jen {len(pos)} z 20 strategií je po nákladech v plusu.** Konkrétně: "
             + ", ".join(f"*{DESC.get(k,{}).get('nazev',k)}*" for k in sorted(pos, key=lambda k:-M[k]['sharpe']))
             + ". Zbylých " + str(20-len(pos)) + " prodělává. To je realistický poměr — většina „známých“ vnitrodenních strategií po započtení nákladů nefunguje.\n")
    L.append("**2. Vítězem je VWAP pásmo s branami** (Sharpe 0,69) — jediná strategie, která má zároveň slušný Sharpe, malý drawdown (−12,5 %) a profit factor 1,20. "
             "Potvrzuje se, co ukázal samostatný výzkum VWAP Trend: **samotné pásmo je průměr (Sharpe 0,15), teprve brány z něj dělají použitelnou strategii** — vynechání dní bez ranní energie zvedne Sharpe 4×.\n")
    L.append("**3. Mean-reversion rodina je masakr.** Všechny čtyři „učebnicové“ reverzní strategie (VWAP reverze, Bollinger fade, RSI(2), odpolední reverze) skončily hluboko v mínusu, tři z nich s drawdownem přes −85 %. "
             "Důvod je pokaždé stejný: obchodují často (RSI(2) 14 tisíc obchodů, VWAP reverze 31 tisíc) a jejich hrubá výhoda je menší než náklady. **Vnitrodenní mean reversion na indexu je nákladová past.**\n")
    L.append("**4. Frekvence zabíjí.** Podívej se na korelaci: strategie s méně než 200 obchody ročně jsou v čele, strategie s tisíci obchody v ocase. "
             "Není to náhoda — každý obchod stojí 2 bps a téměř žádný vnitrodenní signál nemá edge větší než pár bps.\n")
    L.append("**5. Dvě „zadarmo“ anomálie fungují líp než většina aktivních strategií.** Overnight hold (2. místo) a fade gapu (3. místo) nevyžadují žádný indikátor — jen držet přes noc, respektive vsadit na zaplnění gapu. "
             "Overnight efekt je akademicky dobře zdokumentovaný a náš test ho potvrzuje i na Nasdaqu.\n")
    if B:
        L.append(f"**6. Ale pozor — benchmark.** Prosté držení NAS100 dalo za stejné období CAGR {B['cagr']:.1f} % při Sharpe {B['sharpe']:.2f}. "
                 f"Žádná z 20 strategií ho neporazila na absolutním výnosu; vítěz má sice nižší drawdown ({-12.5:.1f} % vs {B['mdd']:.0f} %), ale vydělal méně. "
                 "Hodnota vnitrodenních strategií tedy neleží v honbě za výnosem, ale v **nízkém drawdownu, nulovém nočním riziku a nekorelovanosti** — tedy jako doplněk portfolia, ne jako náhrada indexu.\n")
    L.append("\n### ⚠️ Chycený bug (a proč je to důležité)\n")
    L.append("Při prvním běhu vyšla strategie **Průraz včerejšího high/low** jako jasný vítěz: **Sharpe 2,11 a CAGR 34 %**. "
             "Podle pravidla „Sharpe 2+ je podezřele skvělý“ jsem to prověřil — a našel chybu: strategie plnila vstup přesně na úrovni včerejšího maxima, "
             "jenže **ve 22 % dní trh otevírá už nad touto úrovní** (a ve 13,6 % pod včerejším minimem). Na takových dnech se za tu cenu nikdy neobchodovalo — šlo o *look-ahead*, nákup v ceně, která nebyla k mání. "
             "Po opravě (plnění na openu, pokud trh gapnul přes úroveň) spadla strategie na **Sharpe −0,27 a CAGR −4,1 %** a v žebříčku je na 10. místě. "
             "Rozdíl mezi „nejlepší strategií v testu“ a „ztrátovou strategií“ byl jediný řádek kódu.\n")
    L.append("\n---\n\n## Detailní závěry ke každé strategii\n")
    for i,(k,v) in enumerate(rank,1):
        d=DESC.get(k,{})
        verdict = ("✅ **funguje**" if v["sharpe"] >= 0.35 and v["cagr"] > 0 else
                   "🟡 **hraniční / na nule**" if v["cagr"] > -1.0 else "❌ **nefunguje**")
        L.append(f"### {i}. {d.get('nazev',k)} — {verdict}\n")
        L.append(f"**Rodina:** {d.get('rodina','')}  \n**Parametry:** {d.get('params','')}\n")
        L.append(f"**Co to je:** {d.get('popis','')}\n")
        L.append(f"**Proč by to mělo fungovat:** {d.get('proc','')}\n")
        L.append("| metrika | hodnota | | metrika | hodnota |")
        L.append("|---|---|---|---|---|")
        L.append(f"| CAGR | **{fmt(v['cagr'],2,' %')}** | | celkový výnos | {fmt(v['tot'],1,' %')} |")
        L.append(f"| Sharpe | **{fmt(v['sharpe'])}** | | Calmar | {fmt(v.get('calmar',0))} |")
        L.append(f"| Max drawdown | **{fmt(v['mdd'],2,' %')}** | | profit factor | {fmt(v['pf'])} |")
        L.append(f"| win rate | {fmt(v['win'],1,' %')} | | průměr / obchod | {fmt(v['avgbps'],2,' bps')} |")
        L.append(f"| počet obchodů | {v['n']} | | obchodů / rok | {fmt(v.get('trades_per_year',0),0)} |")
        L.append(f"| MC: kladných scénářů | {fmt(v.get('mc_positive_pct',0),0,' %')} | | MC: medián výnosu | {fmt(v.get('mc_median_ret',0),1,' %')} |")
        L.append(f"| MC: 5. percentil výnosu | {fmt(v.get('mc_p5_ret',0),1,' %')} | | MC: medián MaxDD | {fmt(v.get('mc_median_mdd',0),1,' %')} |")
        yr=v.get("yearly",{})
        if yr:
            pos=sum(1 for x in yr.values() if x>0)
            L.append(f"\n**Roční výnosy:** {' · '.join(f'{y}: {x:+.1f}%' for y,x in sorted(yr.items()))}  \n"
                     f"**Kladných let:** {pos}/{len(yr)}\n")
        L.append(f"\n![equity]({imgdir}/{k}_equity.png)\n")
        L.append(f"![mc fan]({imgdir}/{k}_mc_fan.png)\n")
        L.append(f"![mc cloud]({imgdir}/{k}_mc_cloud.png)\n")
        L.append(f"![yearly]({imgdir}/{k}_yearly.png)\n")
        L.append("\n---\n")
    L.append("\n## Lekce z celého testu\n")
    L.append("1. **Náklady rozhodují víc než signál.** Většina testovaných strategií má kladnou hrubou výhodu — a přesto prodělává. Rozdíl dělá počet obchodů.\n"
             "2. **Filtr je cennější než signál.** VWAP pásmo bez bran: Sharpe 0,15. Se dvěma branami: 0,69. Stejný vstupní signál, čtyřnásobný výsledek — jen se neobchodovalo ve špatné dny.\n"
             "3. **Podezřele skvělý výsledek = hledej bug.** Jediná strategie se Sharpe > 2 byla chyba v kódu. Než uvěříš dobrému číslu, zkus ho rozbít.\n"
             "4. **Win rate nic neříká.** Vítěz má win rate 39 %, nejhorší strategie v testu 46 %. Rozhoduje součin četnosti a velikosti.\n"
             "5. **Slavné indikátorové systémy neobstály.** EMA kříž, Bollinger, RSI(2), Donchian — vše záporné. Populární ≠ funkční.\n"
             "6. **Monte Carlo neřekne, jestli je strategie přeučená** — jen jak moc záleží na pořadí obchodů. Skutečný test je čerstvý OOS.\n")
    L.append("\n## Co dál\n")
    L.append("- **OOS zůstává nedotčené** (2018 – 2020/05, ~2,4 roku). Doporučení: vybrat **jednu** strategii z první trojky, sepsat předem kritéria úspěchu a spustit jediný OOS běh. Jakmile se OOS použije, přestává být čisté.\n"
             "- Kandidát č. 1 je jednoznačně **VWAP pásmo s branami**, které navíc má nezávislé potvrzení z odděleného výzkumu (QuantConnect, reálná NQ data, 2018–2025).\n"
             "- Za zvážení stojí i **kombinace vítěze s overnight efektem** — jsou to prakticky nekorelované zdroje výnosu (jeden vnitrodenní, druhý přesně mimo obchodní hodiny).\n")
    with open(out_md,"w") as f: f.write("\n".join(L))
    print(f"wrote {out_md} ({len(L)} lines, {len(rank)} strategies)")

if __name__=="__main__":
    main(sys.argv[1] if len(sys.argv)>1 else "results/lab/metrics.json",
         sys.argv[2] if len(sys.argv)>2 else "results/LAB_REPORT_CZ.md")
