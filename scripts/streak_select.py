"""Streak-stack selection variants: rules chosen by a 2018-2021 z-score of the
win-rate edge over the random-walk rate (single context filters, 80+ trades),
stacked one trade a day, evaluated on 2018-2021 and on untouched 2022-2025,
plus the pass-rate / time frontier by win size. Usage: streak_select.py DIR
"""
import sys, math, itertools, statistics as st
from collections import defaultdict
sys.path.insert(0,"scripts")
import score_xmkt_streak as X
from prop_sim import Trade
SP=sys.argv[1]; rows=X.load(SP)
fl=[f for f in X.FILTERS if f!="all"]
def scan(combos, min_n):
    groups=defaultdict(list)
    for r in rows: groups[(r["inst"],r["type"])].append(r)
    out=[]
    for (inst,typ),rs in groups.items():
        for cb in combos:
            sel=[r for r in rs if all(X.FILTERS[f](r) for f in cb)]
            a=[r for r in sel if r["date"]<"2022"]; b=[r for r in sel if r["date"]>="2022"]
            if len(a)<min_n or len(b)<15: continue
            for side in (1,-1):
                for ti,si in X.PAIRS:
                    base=X.LEVELS[si]/(X.LEVELS[ti]+X.LEVELS[si])
                    ra=[X.result_bp(r,side,ti,si) for r in a]
                    wa=sum(w for _,w in ra)/len(ra)
                    z=(wa-base)/math.sqrt(base*(1-base)/len(ra))
                    rb=[X.result_bp(r,side,ti,si) for r in b]
                    wb=sum(w for _,w in rb)/len(rb)
                    out.append(dict(z=z,ea=wa-base,eb=wb-base,inst=inst,typ=typ,cb=cb,side=side,ti=ti,si=si,sel=sel,n=len(a)))
    return out
cal=sorted({r["date"] for r in rows})
for label,combos,min_n,zmin in (("single filters, z>=3",[("all",)]+[(f,) for f in fl],80,3.0),
                                ("single filters, z>=4",[("all",)]+[(f,) for f in fl],80,4.0),
                                ("pairs too, z>=4",[("all",)]+[(f,) for f in fl]+list(itertools.combinations(fl,2)),60,4.0)):
    out=[o for o in scan(combos,min_n) if o["z"]>=zmin and o["ea"]>=0.05]
    keep=sum(1 for o in out if o["eb"]>=0.05)
    print(f"\n{label}: {len(out)} rules; edge>=5pp also in 2022-25: {keep} ({keep/max(1,len(out))*100:.0f}%)")
    best={}
    for o in sorted(out,key=lambda o:-o["z"]):
        k=(o["inst"],o["typ"],o["side"])
        if k not in best: best[k]=o
    for top in (3,6,10):
        rules=sorted(best.values(),key=lambda o:-o["z"])[:top]
        first={}
        for o in rules:
            for r in o["sel"]:
                if r["date"] not in first or r["hm"]<first[r["date"]][0]:
                    x,_=X.result_bp(r,o["side"],o["ti"],o["si"])
                    first[r["date"]]=(r["hm"],x/X.LEVELS[o["ti"]]*X.WIN_USD,X.LEVELS[o["si"]]/X.LEVELS[o["ti"]])
        tr=[Trade(d,v[1],"S") for d,v in first.items() if v[2]*X.WIN_USD<=1950]
        a=X.evaluate(tr,cal,"0","2022"); b=X.evaluate(tr,cal,"2022","9")
        names=", ".join(f"{o['typ']}{'L' if o['side']==1 else 'S'}[{'&'.join(o['cb'])}]{X.LEVELS[o['ti']]}/{X.LEVELS[o['si']]}" for o in rules[:3])
        print(f"   top {top:2}: {len(tr)/8:4.0f}/yr | 18-21 WR {a[2]:.0f}% pass {a[0]:.0f}% ({a[1]}d) | 22-25 WR {b[2]:.0f}% pass {b[0]:.0f}% ({b[1]}d)  e.g. {names}")

print("\n== frontier: z>=3 single-filter stack (top 3), win size W vs pass and time")
out=[o for o in scan([("all",)]+[(f,) for f in fl],80) if o["z"]>=3.0 and o["ea"]>=0.05]
best={}
for o in sorted(out,key=lambda o:-o["z"]):
    k=(o["inst"],o["typ"],o["side"])
    if k not in best: best[k]=o
rules=sorted(best.values(),key=lambda o:-o["z"])[:3]
for W in (200,300,400,500,600,800):
    first={}
    for o in rules:
        for r in o["sel"]:
            if r["date"] not in first or r["hm"]<first[r["date"]][0]:
                x,_=X.result_bp(r,o["side"],o["ti"],o["si"])
                first[r["date"]]=(r["hm"],x/X.LEVELS[o["ti"]]*W,X.LEVELS[o["si"]]/X.LEVELS[o["ti"]])
    tr=[Trade(d,v[1],"S") for d,v in first.items() if v[2]*W<=1950]
    a=X.evaluate(tr,cal,"0","2022"); b=X.evaluate(tr,cal,"2022","9")
    print(f"   W ${W:4}: 18-21 pass {a[0]:4.0f}% ({a[1]:3} trading days) | 22-25 pass {b[0]:4.0f}% ({b[1]:3} trading days)")
