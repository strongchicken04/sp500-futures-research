"""FOR FUN — overfitting taken to the ABSURD EXTREME. NOT tradeable, ever."""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orb_backtest import load_rth_1min, Config
EOD=15*60+59
def prep(dd,s,e):
    df=load_rth_1min(Config(data_dir=dd,start_year=s,end_year=e)).copy().sort_values(["date","etmin"]).reset_index(drop=True)
    hlc3=(df["high"]+df["low"]+df["close"])/3.0
    df["vwap"]=(hlc3*df["volume"]).groupby(df["date"]).cumsum()/df["volume"].groupby(df["date"]).cumsum().replace(0,np.nan)
    rows=[(dt,g["open"].iloc[0],g["high"].max(),g["low"].min(),g["close"].iloc[-1]) for dt,g in df.groupby("date",sort=True)]
    d=pd.DataFrame(rows,columns=["date","o","h","l","c"]).set_index("date")
    d["prev_c"]=d["c"].shift(1); d["gap"]=(d["o"]/d["prev_c"]-1).abs()*1e4
    d["tr"]=(d["c"]-d["o"]).abs()/(d["h"]-d["l"]).replace(0,np.nan); d["ptr"]=d["tr"].shift(1)
    days={dt:(g["etmin"].to_numpy(),g["close"].to_numpy(),g["vwap"].to_numpy()) for dt,g in df.groupby("date",sort=True)}
    return d,days
def trades(d,days,band=20.,gap_pct=15.,trend_pct=55.,entry_min=571,cost_bps=1.):
    gapH=[];ptH=[];out=[]
    for date in d.index:
        r=d.loc[date];gap=r["gap"];ytr=r["ptr"]
        def rk(h,v): return None if (v is None or (isinstance(v,float) and np.isnan(v)) or len(h)<60) else float(np.mean(np.array(h)<=v))
        gr=rk(gapH,gap);pr=rk(ptH,ytr)
        gOK=gap_pct<=0 or gr is None or gr>=gap_pct/100.
        pOK=trend_pct>=100 or pr is None or pr<=trend_pct/100.
        if not np.isnan(gap):gapH.append(gap);gapH[:]=gapH[-250:]
        if ytr is not None and not np.isnan(ytr):ptH.append(ytr);ptH[:]=ptH[-250:]
        if not(gOK and pOK) or date not in days: continue
        etm,cl,vw=days[date];b=band/1e4;pos=0;entry=0;tr=False;ret=0
        for j in range(len(etm)):
            if np.isnan(vw[j]):continue
            m=etm[j];up=vw[j]*(1+b);dn=vw[j]*(1-b)
            if m>=EOD:
                if pos!=0:ret=pos*(cl[j]-entry)/entry;pos=0
                break
            if m<entry_min:continue
            c=cl[j]
            if pos==0 and not tr:
                if c>up:pos=1;entry=c;tr=True
                elif c<dn:pos=-1;entry=c;tr=True
            elif pos==1 and c<dn:ret=(c-entry)/entry;pos=0
            elif pos==-1 and c>up:ret=-(c-entry)/entry;pos=0
        if tr:out.append((pd.Timestamp(date),ret-2*cost_bps/1e4))
    return pd.DataFrame(out,columns=["date","ret"])
def met(tr,ALL):
    if len(tr)==0:return dict(sharpe=0,mdd=0,cagr=0,win=0,n=0,eq=pd.Series([1]))
    dr=pd.Series(0.,index=pd.to_datetime(ALL));dr.loc[tr["date"].values]=tr["ret"].values
    sh=dr.mean()/dr.std()*np.sqrt(252) if dr.std() else np.inf
    eq=(1+dr).cumprod();mdd=((eq-eq.cummax())/eq.cummax()).min()*100
    yrs=(dr.index[-1]-dr.index[0]).days/365.25
    return dict(sharpe=sh,mdd=mdd,cagr=((eq.iloc[-1])**(1/yrs)-1)*100,win=(tr["ret"]>0).mean()*100,n=len(tr),eq=eq)
DATA="/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/fsdata/pyfinancialdata/data/currencies/oanda/NAS100_USD"
d,days=prep(DATA,2016,2020);ALL=list(d.index)
def show(t,tr):m=met(tr,ALL);sh=f"{m['sharpe']:.2f}" if np.isfinite(m['sharpe']) else "inf";print(f"{t:46} Sharpe {sh:>6}  CAGR {m['cagr']:6.1f}%  MDD {m['mdd']:6.1f}%  win {m['win']:4.0f}%  n {m['n']}");return m
print("=== OVERFIT: TOTAL EXTREME (NAS100 2016-2020 IS) ===\n")
tr1=trades(d,days,27.5,15,55,571);show("start: greedy-tuned",tr1)
# E1: per-year OPTIMAL band (fit each year's noise)
bands=[10,15,20,25,27.5,30,35];bt={b:trades(d,days,b,15,55,571) for b in bands}
for b in bands: bt[b]["yr"]=bt[b]["date"].dt.year
parts=[]
for yr in range(2016,2021):
    best=max(bands,key=lambda b: met(bt[b][bt[b]["yr"]==yr][["date","ret"]],ALL)["sharpe"])
    parts.append(bt[best][bt[best]["yr"]==yr][["date","ret"]])
trE1=pd.concat(parts);show("E1: + per-YEAR optimal band",trE1)
# E2: weekday x month cell filter (drop every losing cell)
t=trE1.copy();t["wd"]=t["date"].dt.dayofweek;t["mo"]=t["date"].dt.month
cell=t.groupby(["wd","mo"])["ret"].mean();good=set(cell[cell>0].index)
trE2=t[[ (w,m) in good for w,m in zip(t["wd"],t["mo"])]][["date","ret"]];show("E2: + drop losing weekday x month cells",trE2)
# E3: drop worst 30% of weeks
t=trE2.copy();t["wk"]=t["date"].dt.isocalendar().week.astype(int)+t["date"].dt.year*100
wk=t.groupby("wk")["ret"].sum();bad=set(wk[wk<wk.quantile(0.30)].index)
trE3=t[~t["wk"].isin(bad)][["date","ret"]];show("E3: + delete worst 30% of weeks",trE3)
# E4: drop worst 20% of individual trades
trE4=trE3.sort_values("ret").iloc[int(len(trE3)*0.20):][["date","ret"]];show("E4: + delete worst 20% of trades",trE4)
# E5 THE LIMIT: keep ONLY winning trades
trE5=trE1[trE1["ret"]>0][["date","ret"]];show("E5: keep ONLY winners (100% win) <- the limit",trE5)
import matplotlib;matplotlib.use("Agg");import matplotlib.pyplot as plt
fig,ax=plt.subplots(figsize=(10,5.5))
seq=[("start tuned",tr1,"#999"),("E1 per-year band",trE1,"#1f77b4"),("E2 weekday×month",trE2,"#9467bd"),("E3 drop weeks",trE3,"#ff7f0e"),("E4 drop trades",trE4,"#8c564b"),("E5 ONLY winners",trE5,"#d62728")]
for tag,tr,c in seq:
    m=met(tr,ALL);sh=f"{m['sharpe']:.1f}" if np.isfinite(m['sharpe']) else "∞"
    ax.plot(m["eq"].index,m["eq"].values,label=f"{tag}: Sharpe {sh}",lw=1.5,color=c)
ax.set_yscale("log");ax.set_title("OVERFIT — TOTAL EXTREME (NAS100 2016-2020, IS)\nfrom a real strategy to a perfect fantasy — FOR FUN, 100% fake")
ax.set_ylabel("equity (log)");ax.legend(fontsize=8,loc="upper left");ax.grid(True,which="both",alpha=0.25)
fig.tight_layout();fig.savefig("../results/vwap_overfit_extreme.png",dpi=130);print("\nsaved vwap_overfit_extreme.png")
