"""Does Monte Carlo catch the overfit? (1) bootstrap-MC on cherry-picked trades
passes with flying colours; (2) the real test = run the same overfit machine on
PURE RANDOM data (no edge by construction) and watch it manufacture Sharpe."""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orb_backtest import load_rth_1min, Config
EOD=15*60+59
rng=np.random.default_rng(7)

def build(df):
    df=df.sort_values(["date","etmin"]).reset_index(drop=True)
    hlc3=(df["high"]+df["low"]+df["close"])/3.0
    df["vwap"]=(hlc3*df["volume"]).groupby(df["date"]).cumsum()/df["volume"].groupby(df["date"]).cumsum().replace(0,np.nan)
    rows=[(dt,g["open"].iloc[0],g["high"].max(),g["low"].min(),g["close"].iloc[-1]) for dt,g in df.groupby("date",sort=True)]
    d=pd.DataFrame(rows,columns=["date","o","h","l","c"]).set_index("date")
    d["prev_c"]=d["c"].shift(1); d["gap"]=(d["o"]/d["prev_c"]-1).abs()*1e4
    d["tr"]=(d["c"]-d["o"]).abs()/(d["h"]-d["l"]).replace(0,np.nan); d["ptr"]=d["tr"].shift(1)
    days={dt:(g["etmin"].to_numpy(),g["close"].to_numpy(),g["vwap"].to_numpy()) for dt,g in df.groupby("date",sort=True)}
    return d,days
def trades(d,days,band,gap_pct,trend_pct,entry_min=571,cost_bps=1.):
    gapH=[];ptH=[];out=[]
    for date in d.index:
        r=d.loc[date];gap=r["gap"];ytr=r["ptr"]
        def rk(h,v): return None if (v is None or (isinstance(v,float) and np.isnan(v)) or len(h)<60) else float(np.mean(np.array(h)<=v))
        gr=rk(gapH,gap);pr=rk(ptH,ytr)
        gOK=gap_pct<=0 or gr is None or gr>=gap_pct/100.;pOK=trend_pct>=100 or pr is None or pr<=trend_pct/100.
        if not np.isnan(gap):gapH.append(gap);gapH[:]=gapH[-250:]
        if ytr is not None and not np.isnan(ytr):ptH.append(ytr);ptH[:]=ptH[-250:]
        if not(gOK and pOK) or date not in days:continue
        etm,cl,vw=days[date];b=band/1e4;pos=0;entry=0;t=False;ret=0
        for j in range(len(etm)):
            if np.isnan(vw[j]):continue
            m=etm[j];up=vw[j]*(1+b);dn=vw[j]*(1-b)
            if m>=EOD:
                if pos!=0:ret=pos*(cl[j]-entry)/entry;pos=0
                break
            if m<entry_min:continue
            c=cl[j]
            if pos==0 and not t:
                if c>up:pos=1;entry=c;t=True
                elif c<dn:pos=-1;entry=c;t=True
            elif pos==1 and c<dn:ret=(c-entry)/entry;pos=0
            elif pos==-1 and c>up:ret=-(c-entry)/entry;pos=0
        if t:out.append((pd.Timestamp(date),ret-2*cost_bps/1e4))
    return pd.DataFrame(out,columns=["date","ret"])
def sharpe_of(tr,ALL):
    if len(tr)==0:return 0
    dr=pd.Series(0.,index=pd.to_datetime(ALL));dr.loc[tr["date"].values]=tr["ret"].values
    return dr.mean()/dr.std()*np.sqrt(252) if dr.std() else 0
def overfit(d,days,ALL):
    best=(20,25,60);bs=sharpe_of(trades(d,days,20,25,60),ALL)
    for b in [10,15,20,25,30,35]:
        s=sharpe_of(trades(d,days,b,best[1],best[2]),ALL)
        if s>bs:bs=s;best=(b,best[1],best[2])
    for gp in [0,15,25,35,50]:
        s=sharpe_of(trades(d,days,best[0],gp,best[2]),ALL)
        if s>bs:bs=s;best=(best[0],gp,best[2])
    for tp in [40,55,70,100]:
        s=sharpe_of(trades(d,days,best[0],best[1],tp),ALL)
        if s>bs:bs=s;best=(best[0],best[1],tp)
    tr=trades(d,days,*best)
    # + hindsight weekday x month + drop worst 20% weeks
    t=tr.copy();t["wd"]=t["date"].dt.dayofweek;t["mo"]=t["date"].dt.month
    cell=t.groupby(["wd","mo"])["ret"].mean();good=set(cell[cell>0].index)
    t=t[[(w,m) in good for w,m in zip(t["wd"],t["mo"])]]
    t["wk"]=t["date"].dt.isocalendar().week.astype(int)+t["date"].dt.year*100
    wk=t.groupby("wk")["ret"].sum();t=t[~t["wk"].isin(set(wk[wk<wk.quantile(0.20)].index))]
    return best,sharpe_of(tr,ALL),sharpe_of(t[["date","ret"]],ALL)

# ---------- PART 1: bootstrap MC on cherry-picked (winners-only) trades ----------
DATA="/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/fsdata/pyfinancialdata/data/currencies/oanda/NAS100_USD"
rdf=load_rth_1min(Config(data_dir=DATA,start_year=2016,end_year=2020)).copy()
d,days=build(rdf);ALL=list(d.index)
tr=trades(d,days,27.5,15,55);winners=tr[tr["ret"]>0]["ret"].to_numpy()
sims=[]
for _ in range(5000):
    s=rng.choice(winners,size=len(winners),replace=True)
    sims.append((1+s).prod()-1)
sims=np.array(sims)
print("PART 1 — bootstrap MC on the CHERRY-PICKED (winners-only) trade pool:")
print(f"  scenarios positive: {(sims>0).mean()*100:.1f}%   median total: {np.median(sims)*100:.0f}%   5th pct: {np.percentile(sims,5)*100:.0f}%")
print("  -> MC says: FLAWLESS. It resamples winners, so every path wins. It CANNOT see the selection.\n")

# ---------- PART 2: run the SAME overfit machine on PURE RANDOM data ----------
print("PART 2 — run the overfit machine on PURE RANDOM-WALK data (no edge exists):")
def synth(ndays=1124, seed=1):
    r=np.random.default_rng(seed);rows=[];px=15000.0
    dates=pd.bdate_range("2016-01-04",periods=ndays)
    for dt in dates:
        px*= (1+r.normal(0,0.008))  # overnight
        o=px
        for m in range(570,960):
            px*=(1+r.normal(0,0.0006))  # per-min random walk, ~1.2% daily vol
            hi=px*(1+abs(r.normal(0,0.0003)));lo=px*(1-abs(r.normal(0,0.0003)))
            rows.append((dt.strftime("%Y-%m-%d"),m,o if m==570 else px,hi,lo,px,r.integers(50,500)))
            o=px
    return pd.DataFrame(rows,columns=["date","etmin","open","high","low","close","volume"])
res=[]
for seed in range(6):
    sdf=synth(seed=seed);sd,sdays=build(sdf);sALL=list(sd.index)
    best,base_s,of_s=overfit(sd,sdays,sALL)
    res.append((base_s,of_s));print(f"  random dataset #{seed}: tuned Sharpe {base_s:.2f}  ->  after hindsight filters {of_s:.2f}   (params {best})")
res=np.array(res)
print(f"\n  AVERAGE Sharpe manufactured from PURE NOISE: tuned {res[:,0].mean():.2f}, fully overfit {res[:,1].mean():.2f}")
print("  -> The overfit machine invents Sharpe ~2-3 out of data with ZERO real edge. THAT is the proof.")
