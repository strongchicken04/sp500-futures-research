#!/usr/bin/env python3
"""Build the historical instrument-classification file imported into QuantConnect (Object Store) for the
extreme-upside study (Stage 2, option A, owner decision 2026-11-25).

Sources (public, downloaded to a local cache directory; the output is imported INTO QC, nothing leaves QC):
  S1 SEC "Investment Company Series and Class Information", yearly files 2010-2026
     (https://www.sec.gov/open/datasets-investment_company.html). Open-end '40-Act funds (org type 30) with a
     1-4 letter class ticker = exchange-traded fund share classes (mutual fund classes carry 5-letter ...X
     tickers). Yearly snapshots INCLUDE funds that were later liquidated -> survivorship-free from 2010 at
     yearly resolution. Series ID links ticker changes. Not covered: UITs (SPY, QQQ, DIA), commodity pools /
     grantor trusts (GLD, USO, UVXY, GBTC), ETNs (bank notes), closed-end funds (no class tickers).
  S2 SEC company_tickers_exchange.json (current): ticker -> registrant name / CIK / exchange.
  S3 Nasdaq Trader symbol directories nasdaqlisted.txt / otherlisted.txt (current): security name, ETF flag,
     test-issue flag, listing exchange. ETNs carry ETF = N (e.g. VXX) -> detected by name.
  Current sources (S2, S3) say what an instrument IS today; inside QC they are applied only to the security id
  that holds the ticker on the latest data dates, and from there to that security's whole history (QC security
  ids survive ticker changes; a reused ticker is a different id).
Output (pipe-separated): type|ticker|start|end|exchange|source|id|name
  start / end: YYYY-MM-DD effective range for S1 (first file year - 1 .. last file year), CUR for S2/S3.
"""
import csv, glob, json, os, re, sys, urllib.request, collections

UA = {"User-Agent": "research-client admin@example.com"}
CACHE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/xdl"
OUT = sys.argv[2] if len(sys.argv) > 2 else "instrument_class.psv"
BAD = {"", "NULL", "N/A", "NA", "NONE", "TBD", "XXXX"}


def fetch(url, path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
    return path


def year_of(fn):
    m = re.search(r"(20\d\d)", os.path.basename(fn))
    return int(m.group(1)) if m else 2016          # the un-versioned file sits between 2015 and 2017


def load_sec(fn):
    rows = list(csv.reader(open(fn, encoding="utf-8-sig", errors="replace")))
    for i, r in enumerate(rows[:10]):
        low = [c.lower() for c in r]
        if any("ticker" in c for c in low):
            break
    else:
        return []

    def col(*keys):
        for k in keys:
            for j, c in enumerate(low):
                if k in c:
                    return j
    c = dict(tk=col("ticker"), typ=col("org type", "org_type", "entity_org"), cik=col("cik"),
             ser=col("series id", "series_id"), sname=col("series name", "series_name"))
    out = []
    for r in rows[i + 1:]:
        if len(r) <= c["tk"]:
            continue
        t = r[c["tk"]].strip().upper()
        if t in BAD or not re.fullmatch(r"[A-Z]{1,4}", t):
            continue
        if r[c["typ"]].strip() != "30":
            continue
        out.append((t, r[c["ser"]].strip(), r[c["sname"]].strip(), r[c["cik"]].strip().lstrip("0")))
    return out


def classify_name(name, etf_flag, test):
    n = name.upper()
    if test:
        return "TEST"
    if re.search(r"\bETNS?\b|EXCHANGE[- ]TRADED NOTE|\bIPATH\b|ETRACS|VELOCITYSHARES|\bELEMENTS\b|MICROSECTORS|X-?LINKS", n):
        return "ETN"
    if etf_flag:
        return "ETF"
    if re.search(r"\bWARRANTS?\b", n):
        return "WARRANT"
    if re.search(r"\bRIGHTS?\b", n):
        return "RIGHT"
    if re.search(r"PREFERRED|PREFERENCE", n) and re.search(r"\bUNITS?\b|SHARES|SECURITIES", n):
        return "PREFERRED"
    if re.search(r"\bUNITS?\b", n) and not re.search(r"COMMON UNITS|LIMITED PARTNERSHIP|DEPOSITARY UNIT|REPRESENTING", n):
        return "UNIT"
    if re.search(r"AMERICAN DEPOSIT[AO]RY|\bADS\b|\bADR\b", n):
        return "ADR"
    if re.search(r"NOTES? DUE|DEBENTURE|SENIOR NOTE|SUBORDINATED|% NOTES|\bNOTES\b", n):
        return "DEBT"
    if re.search(r"PREFERRED|\bPFD\b|DEPOSITARY SHARES|PERPETUAL|CUMULATIVE|% SERIES|FIXED[- ]RATE RESET|FIXED-TO-FLOATING", n):
        return "PREFERRED"
    if re.search(r"\bFUND\b|\bFUND,|MUNICIPAL|CLOSED[- ]END|BOND TRUST|INCOME TRUST|OPPORTUNITIES TRUST|STRATEGIC INCOME", n) and not re.search(r"REIT|REALTY|BANCORP|ROYALTY", n):
        return "CEF"
    if re.search(r"\bTRUST\b|\bTR\b|SHARES OF BENEFICIAL|\bOPP|DIVIDEND|INCOME|MUNI|BUY-?WRITE|COMMON SHARES", n) and re.search(r"^(BLACKROCK|NUVEEN|EATON VANCE|PIMCO|ABRDN|ABERDEEN|COHEN & STEERS|CALAMOS|GABELLI|DOUBLELINE|TEMPLETON|WESTERN ASSET|INVESCO|MFS|PUTNAM|ALLIANCEBERNSTEIN|KAYNE|TORTOISE|CLEARBRIDGE|VIRTUS|FLAHERTY|JOHN HANCOCK|DWS|NEUBERGER|BLACKSTONE|APOLLO|ADAMS|GENERAL AMERICAN|ROYCE|LIBERTY ALL|TRI-CONTINENTAL|SPECIAL OPPORTUNITIES|HIGHLAND|ALLSPRING|WELLS FARGO|MORGAN STANLEY|BNY|DREYFUS|FEDERATED|PIONEER|AMERICAN STRATEGIC|SALOMON|LMP|PGIM|THE CHINA|THE INDIA|MEXICO|KOREA|ASA GOLD)", n):
        return "CEF"
    if re.search(r"COMMON|ORDINARY SHARE|CLASS [A-Z]\b|SHARES|COMMON UNITS|LIMITED PARTNERSHIP|DEPOSITARY UNIT|ROYALTY|STOCK|\bINC\b|\bCORP|\bLTD\b|\bPLC\b|\bASA\b|N\.V\.|S\.A\.|L\.P\.|HOLDINGS|GROUP|LIMITED|COMPANY", n):
        return "COMMON"
    return "OTHER"


MON = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def fetch_ncen(cache):
    """S4 SEC Form N-CEN data sets (2018q3-), https://www.sec.gov/data-research/sec-markets-data/form-n-cen-data-sets:
    SECURITY_EXCHANGE (ETF / UIT tickers, e.g. SPY, QQQ, DIA as S-6 UITs) and SECURITY_RELATED_ITEM (closed-end
    fund common / preferred / debt tickers, N-2), each with the report period end date. Extracted to ncen_rows.tsv."""
    import zipfile, io
    outp = os.path.join(cache, "ncen_rows.tsv")
    if os.path.exists(outp):
        return outp
    page = urllib.request.urlopen(urllib.request.Request("https://www.sec.gov/data-research/sec-markets-data/form-n-cen-data-sets", headers=UA), timeout=60).read().decode()
    paths = sorted(set(re.findall(r'href="(/files/dera/data/form-n-cen-data-sets/[^"]+\.zip)"', page)))
    with open(outp, "w") as out:
        for pth in paths:
            zp = os.path.join(cache, os.path.basename(pth))
            fetch("https://www.sec.gov" + pth, zp)
            z = zipfile.ZipFile(zp)

            def rd(f):
                r = csv.reader(io.TextIOWrapper(z.open(f), encoding="utf-8", errors="replace"), delimiter="\t")
                return next(r), r
            h, r = rd("SUBMISSION.tsv"); sub = {x[h.index("ACCESSION_NUMBER")]: x[h.index("REPORT_ENDING_PERIOD")] for x in r if len(x) > h.index("REPORT_ENDING_PERIOD")}
            h, r = rd("REGISTRANT.tsv"); typ = {x[h.index("ACCESSION_NUMBER")]: x[h.index("INVESTMENT_COMPANY_TYPE")] for x in r if len(x) > h.index("INVESTMENT_COMPANY_TYPE")}
            h, r = rd("SECURITY_EXCHANGE.tsv")
            for x in r:
                if len(x) >= 3:
                    a = x[0].split("_")[0]
                    out.write("\t".join(["SE", x[2].strip().upper(), x[1], sub.get(a, ""), typ.get(a, ""), "", ""]) + "\n")
            if "SECURITY_RELATED_ITEM.tsv" in z.namelist():
                h, r = rd("SECURITY_RELATED_ITEM.tsv")
                for x in r:
                    if len(x) >= 7:
                        a = x[0].split("_")[0]
                        out.write("\t".join(["SR", x[6].strip().upper(), x[5], sub.get(a, ""), typ.get(a, ""), x[2][:30], x[3][:60]]) + "\n")
            os.remove(zp)
    return outp


def ncen_rows(cache):
    import datetime as _dt
    agg = {}
    for ln in open(fetch_ncen(cache)):
        p = ln.rstrip("\n").split("\t")
        if len(p) < 7:
            continue
        kind, tk, ex, per, ictype, desc = p[0], p[1], p[2], p[3], p[4], p[5]
        if not re.fullmatch(r"[A-Z]{1,5}(\.[A-Z]{1,3})?", tk) or tk in BAD or (len(tk) == 5 and tk.endswith("X")):
            continue
        m = re.fullmatch(r"(\d\d)-([A-Z]{3})-(\d{4})", per)
        if not m:
            continue
        d = _dt.date(int(m.group(3)), MON[m.group(2)], int(m.group(1)))
        if kind == "SE":
            t = "ETF"
        else:
            dl = desc.lower()
            t = "PREFERRED" if "preferred" in dl else "DEBT" if ("bond" in dl or "convertible" in dl) else "WARRANT" if "warrant" in dl else "CEF"
        k = (t, tk)
        a, b = agg.get(k, (d, d))
        agg[k] = (min(a, d), max(b, d))
    rows = []
    for (t, tk), (a, b) in agg.items():
        st = a - _dt.timedelta(days=400)
        en = b + _dt.timedelta(days=120)
        rows.append((t, tk, st.isoformat(), en.isoformat(), "", "NCEN", "", ""))
    return rows


def main():
    os.makedirs(CACHE, exist_ok=True)
    rows = []
    # S1 yearly SEC files (already cached by the download step; listed on the SEC page)
    agg = collections.defaultdict(set)      # (series, ticker) -> years
    names = {}
    for fn in sorted(glob.glob(os.path.join(CACHE, "*series*class*.csv"))):
        y = year_of(fn)
        for t, ser, sname, cik in load_sec(fn):
            agg[(ser, t)].add(y)
            names[(ser, t)] = sname
    tick_by_series = collections.defaultdict(set)
    for (ser, t), ys in agg.items():
        tick_by_series[ser].add(t)
        rows.append(("ETF", t, f"{min(ys) - 1}-01-01", f"{max(ys)}-12-31", "", "SEC-SC", ser, names[(ser, t)][:60]))
    changes = sum(1 for s, ts in tick_by_series.items() if len(ts) > 1)
    nc = ncen_rows(CACHE)
    rows += nc
    print("N-CEN rows", len(nc), dict(collections.Counter(r[0] for r in nc)))
    # S2 + S3 current
    cte = json.load(open(fetch("https://www.sec.gov/files/company_tickers_exchange.json", os.path.join(CACHE, "cte.json"))))
    sec_name = {r[2].upper(): (r[1], str(r[0]), r[3]) for r in cte["data"]}
    cur = {}
    nl = fetch("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", os.path.join(CACHE, "nasdaqlisted.txt"))
    for r in csv.DictReader(open(nl), delimiter="|"):
        if r["Symbol"].startswith("File Creation"):
            continue
        cur[r["Symbol"].upper()] = (r["Security Name"], r["ETF"] == "Y", r["Test Issue"] == "Y", "NASDAQ")
    ol = fetch("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", os.path.join(CACHE, "otherlisted.txt"))
    exm = {"N": "NYSE", "A": "NYSEAMER", "P": "ARCA", "Z": "CBOEBZX", "V": "IEX"}
    for r in csv.DictReader(open(ol), delimiter="|"):
        s = r["ACT Symbol"]
        if s.startswith("File Creation"):
            continue
        # QC tickers use '.' for share classes / suffixes (BRK.B); Nasdaq Trader ACT symbols use '.' as well
        cur[s.upper()] = (r["Security Name"], r["ETF"] == "Y", r["Test Issue"] == "Y", exm.get(r["Exchange"], r["Exchange"]))
    tcount = collections.Counter()
    for t, (nm, etf, test, ex) in cur.items():
        typ = classify_name(nm, etf, test)
        # ETN cross-check via the SEC registrant: a ticker registered by a bank that is not the bank's own stock
        sn = sec_name.get(t)
        if typ in ("ETF", "OTHER", "DEBT") and sn and re.search(r"\bBANK\b|\bPLC\b|CREDIT SUISSE|BARCLAYS|UBS AG|DEUTSCHE BANK|JPMORGAN CHASE|MORGAN STANLEY|GOLDMAN SACHS|CITIGROUP|BNP|ROYAL BANK", sn[0].upper()) and re.search(r"NOTE|ETN|LINKED|INDEX", nm.upper()):
            typ = "ETN"
        tcount[typ] += 1
        rows.append((typ, t, "CUR", "CUR", ex, "NASDAQTRADER", sn[1] if sn else "", nm[:60].replace("|", "/")))
    # S2 tickers absent from S3 (e.g. OTC-quoted registrants): only as weak evidence, type from the registrant name
    for t, (nm, cik, ex) in sec_name.items():
        if t in cur:
            continue
        typ = "ETF" if re.search(r"\bETF\b|\bTRUST\b.*\b(SHARES|ETF)\b|PROSHARES|ISHARES|SPDR", nm.upper()) else classify_name(nm, False, False)
        rows.append((typ, t, "CUR", "CUR", (ex or "").upper(), "SEC-CTE", cik, nm[:60].replace("|", "/")))
    with open(OUT, "w") as f:
        f.write("type|ticker|start|end|exchange|source|id|name\n")
        for r in rows:
            f.write("|".join(r) + "\n")
    print(f"rows {len(rows)} | SEC-SC ETF series-ticker rows {len(agg)} series with ticker changes {changes} | current types {dict(tcount)}")


if __name__ == "__main__":
    main()


def write_qc_parts(psv_path, out_dir, limit=29000):
    """Plain-text project files for QC (no compression / encoding allowed; 32k characters per file):
      E y1 y2 T1,T2,...        SEC series/class ETF tickers effective y1..y2
      K y1 y2 TYPE T1,T2,...   N-CEN tickers (ETF incl. UITs, CEF, PREFERRED, DEBT) effective y1..y2
      C TYPE EXCH T1,T2,...    current type (Nasdaq Trader; SECCTE = SEC company tickers for ETF/ETN/CEF only)"""
    E, K, C = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(set)
    for ln in open(psv_path).read().split("\n")[1:]:
        p = ln.split("|")
        if len(p) < 8:
            continue
        if p[5] == "SEC-SC":
            E[(p[2][:4], p[3][:4])].add(p[1])
        elif p[5] == "NCEN":
            K[(p[2][:4], p[3][:4], p[0])].add(p[1])
        elif p[5] == "NASDAQTRADER":
            C[(p[0], p[4] or "-")].add(p[1])
        elif p[0] in ("ETF", "ETN", "CEF"):
            C[(p[0], "SECCTE")].add(p[1])
    lines = [("E %s %s" % k, v) for k, v in sorted(E.items())] + [("K %s %s %s" % k, v) for k, v in sorted(K.items())] + [("C %s %s" % k, v) for k, v in sorted(C.items())]
    out, files, buf = [], [], []
    for head, toks in lines:
        cur = []
        for t in sorted(toks):
            if len(head) + 1 + len(",".join(cur + [t])) > 1900:
                out.append(head + " " + ",".join(cur)); cur = []
            cur.append(t)
        if cur:
            out.append(head + " " + ",".join(cur))
    for l in out:
        if sum(len(x) + 1 for x in buf) + len(l) > limit:
            files.append(buf); buf = []
        buf.append(l)
    files.append(buf)
    for i, b in enumerate(files):
        with open(os.path.join(out_dir, f"xup_ic_{i}.py"), "w") as f:
            f.write(f"# Imported instrument classification part {i + 1}/{len(files)} (plain text). E = SEC series/class ETF tickers,\n"
                    "# K = SEC Form N-CEN tickers by type, C = current Nasdaq Trader / SEC types. Built by\n"
                    "# research/extreme_upside/instrument_class/build_instrument_class.py\n")
            f.write('DATA = """\n' + "\n".join(b) + '\n"""\n')
    return len(files)


if __name__ == "__main__" and len(sys.argv) > 3:
    print("QC project files", write_qc_parts(OUT, sys.argv[3]))
