"""Run all 20 strategies, save metrics JSON + charts."""
import sys, os, json, pickle, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import (build_cache, add_gates, run_strategy, metrics, charts, STRATEGIES, IS)

def main(y0, y1, outdir, only=None, do_charts=True):
    t0=time.time()
    days, dates, ctx = build_cache()
    print(f"[data] {len(dates)} days {dates[0]}..{dates[-1]}  ({time.time()-t0:.0f}s)", flush=True)
    ctx = add_gates(ctx)
    win = [d for d in dates if y0 <= int(d[:4]) <= y1]
    os.makedirs(outdir, exist_ok=True)
    res = {}
    names = only or list(STRATEGIES)
    for i, name in enumerate(names, 1):
        ts=time.time()
        t = run_strategy(name, days, dates, ctx, y0, y1)
        m = metrics(t, win)
        extra = charts(name, m, outdir) if (do_charts and m["n"]>0) else {}
        rec = {k: (round(v,4) if isinstance(v,(int,float,np.floating)) else v)
               for k,v in m.items() if k not in ("daily","equity")}
        rec.update(extra); rec["family"]=STRATEGIES[name][1]
        res[name]=rec
        t.to_csv(f"{outdir}/{name}_trades.csv", index=False)
        print(f"[{i:2d}/{len(names)}] {name:22} n={m['n']:6d} CAGR={m['cagr']:+7.2f}% "
              f"Sharpe={m['sharpe']:+5.2f} MDD={m['mdd']:7.2f}% PF={m['pf']:.2f} ({time.time()-ts:.0f}s)", flush=True)
    with open(f"{outdir}/metrics.json","w") as f:
        json.dump(res, f, indent=2, default=str)
    print(f"TOTAL {time.time()-t0:.0f}s -> {outdir}/metrics.json", flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--y0",type=int,default=IS[0]); p.add_argument("--y1",type=int,default=IS[1])
    p.add_argument("--out",default="results/lab"); p.add_argument("--only",nargs="*")
    p.add_argument("--no-charts",action="store_true")
    a=p.parse_args()
    main(a.y0,a.y1,a.out,a.only,not a.no_charts)
