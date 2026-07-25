"""When did the EMA9+VWAP-wick bounce work best? Conditional analysis of GROSS
per-trade returns (cost hurdle ~2 bps round-trip shown for reference)."""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ema_vwap.ema_vwap_test import to_3min, enrich
from orb_backtest import load_rth_1min, Config

def run_rec(bars):
    o=bars["open"].to_numpy();hi=bars["high"].to_numpy();lo=bars["low"].to_numpy()
    cl=bars["close"].to_numpy();vw=bars["vwap"].to_numpy();em=bars["ema"].to_numpy()
    dc=bars["daycode"].to_numpy();etm=bars["etmin"].to_numpy()
    dts=bars["date"].to_numpy()
    n=len(bars);pos=0;entry=0.;e_et=0;e_dt=None;rec=[]
    for k in range(n-1):
        nd=dc[k+1]!=dc[k]
        if np.isnan(vw[k]) or np.isnan(em[k]):
            if pos!=0 and nd: rec.append((e_dt,e_et,pos,pos*(cl[k]-entry)/entry)); pos=0
            continue
        if pos==0:
            sig=0
            if lo[k]<vw[k] and cl[k]>vw[k]: sig=1
            elif hi[k]>vw[k] and cl[k]<vw[k]: sig=-1
            if sig!=0 and not nd: pos=sig;entry=o[k+1];e_et=etm[k];e_dt=dts[k]
        else:
            ex=False;xpx=o[k+1]
            if pos==1 and cl[k]<em[k]: ex=True
            elif pos==-1 and cl[k]>em[k]: ex=True
            if nd: ex=True;xpx=cl[k]
            if ex: rec.append((e_dt,e_et,pos,pos*(xpx-entry)/entry));pos=0
    t=pd.DataFrame(rec,columns=["date","etmin","dir","ret"])
    t["date"]=pd.to_datetime(t["date"]);t["retbps"]=t["ret"]*1e4
    return t

DATA="/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/fsdata/pyfinancialdata/data/currencies/oanda/NAS100_USD"
b3=enrich(to_3min(load_rth_1min(Config(data_dir=DATA,start_year=2016,end_year=2020))))
t=run_rec(b3)
# daily features
dd=b3.groupby("date").agg(o=("open","first"),h=("high","max"),l=("low","min"),c=("close","last"))
dd.index=pd.to_datetime(dd.index)
dd["range_pct"]=(dd["h"]-dd["l"])/dd["o"]*100
dd["trendiness"]=(dd["c"]-dd["o"]).abs()/(dd["h"]-dd["l"])   # 1=pure trend, 0=round trip
dd["rvol20"]=dd["c"].pct_change().rolling(20).std().shift(1)*np.sqrt(252)  # ex-ante
t=t.join(dd[["range_pct","trendiness","rvol20"]],on="date")
COST=2.0
def tab(t,by,labels,title,qs=True):
    d=t.dropna(subset=[by]).copy()
    d["b"]=pd.qcut(d[by],len(labels),labels=labels,duplicates="drop") if qs else d[by]
    g=d.groupby("b",observed=True)["retbps"]
    print(f"\n=== {title}  (gross bps/trade; cost hurdle ~{COST} bps) ===")
    for lab,m in g.mean().items():
        net=m-COST; flag="  <= beats cost" if net>0 else ""
        print(f"  {str(lab):14} gross {m:+6.2f}   win {(d[d['b']==lab]['retbps']>0).mean()*100:4.0f}%   n {int((d['b']==lab).sum()):5d}   net {net:+6.2f}{flag}")

print(f"total trades {len(t)}, overall gross {t['retbps'].mean():+.2f} bps (cost hurdle {COST})")
t["hour"]=(t["etmin"]//60)
tab(t,"hour",sorted(t["hour"].unique()),"BY ENTRY HOUR (ET)",qs=False)
tab(t,"trendiness",["range(lo)","mid","trend(hi)"],"BY DAY TYPE (trendiness)")
tab(t,"range_pct",["tight","mid","wide"],"BY DAY RANGE")
tab(t,"rvol20",["loVol","midVol","hiVol"],"BY PRIOR VOL (ex-ante)")
print("\nBY DIRECTION:")
for dv,nm in [(1,"long"),(-1,"short")]:
    s=t[t["dir"]==dv]["retbps"]; print(f"  {nm:5} gross {s.mean():+.2f}  win {(s>0).mean()*100:.0f}%  n {len(s)}")
# best combined cell: range-day + midday
best=t[(t["trendiness"]<t["trendiness"].quantile(0.33)) & (t["hour"].between(11,13))]["retbps"]
print(f"\nBEST simple combo (low-trend day + 11:00-14:00): gross {best.mean():+.2f} bps  win {(best>0).mean()*100:.0f}%  n {len(best)}  net {best.mean()-COST:+.2f}")
