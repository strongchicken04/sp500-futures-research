"""FOR FUN — deliberately overfit the VWAP-band strategy on NAS100 2016-2020 (IS,
zero discipline) to show how absurd a curve-fit backtest can look. NOT tradeable."""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orb_backtest import load_rth_1min, Config
EOD = 15*60+59

def prep(data_dir, s, e):
    df = load_rth_1min(Config(data_dir=data_dir, start_year=s, end_year=e)).copy().sort_values(["date","etmin"]).reset_index(drop=True)
    hlc3=(df["high"]+df["low"]+df["close"])/3.0
    cpv=(hlc3*df["volume"]).groupby(df["date"]).cumsum(); cv=df["volume"].groupby(df["date"]).cumsum()
    df["vwap"]=cpv/cv.replace(0,np.nan)
    rows=[]
    for date,g in df.groupby("date",sort=True):
        rows.append((date,g["open"].iloc[0],g["high"].max(),g["low"].min(),g["close"].iloc[-1]))
    d=pd.DataFrame(rows,columns=["date","o","h","l","c"]).set_index("date")
    d["prev_c"]=d["c"].shift(1); d["gap"]=(d["o"]/d["prev_c"]-1).abs()*1e4
    d["tr"]=(d["c"]-d["o"]).abs()/(d["h"]-d["l"]).replace(0,np.nan); d["ptr"]=d["tr"].shift(1)
    days={dt:(g["etmin"].to_numpy(),g["close"].to_numpy(),g["vwap"].to_numpy()) for dt,g in df.groupby("date",sort=True)}
    return d, days

def trades(d, days, band=20.0, gap_pct=25.0, trend_pct=60.0, entry_min=571, cost_bps=1.0):
    gapH=[]; ptH=[]; out=[]
    for date in d.index:
        r=d.loc[date]; gap=r["gap"]; ytr=r["ptr"]
        def rk(h,v): return None if (v is None or (isinstance(v,float) and np.isnan(v)) or len(h)<60) else float(np.mean(np.array(h)<=v))
        gr=rk(gapH,gap); pr=rk(ptH,ytr)
        gOK=gap_pct<=0 or gr is None or gr>=gap_pct/100.0
        pOK=trend_pct>=100 or pr is None or pr<=trend_pct/100.0
        if not np.isnan(gap): gapH.append(gap); gapH[:]=gapH[-250:]
        if ytr is not None and not np.isnan(ytr): ptH.append(ytr); ptH[:]=ptH[-250:]
        if not(gOK and pOK) or date not in days: continue
        etm,cl,vw=days[date]; b=band/1e4; pos=0; entry=0; traded=False; ret=0
        for j in range(len(etm)):
            if np.isnan(vw[j]): continue
            m=etm[j]; up=vw[j]*(1+b); dn=vw[j]*(1-b)
            if m>=EOD:
                if pos!=0: ret=pos*(cl[j]-entry)/entry; pos=0
                break
            if m<entry_min: continue
            c=cl[j]
            if pos==0 and not traded:
                if c>up: pos=1; entry=c; traded=True
                elif c<dn: pos=-1; entry=c; traded=True
            elif pos==1 and c<dn: ret=(c-entry)/entry; pos=0
            elif pos==-1 and c>up: ret=-(c-entry)/entry; pos=0
        if traded: out.append((pd.Timestamp(date), ret-2*cost_bps/1e4))
    return pd.DataFrame(out, columns=["date","ret"])

def metrics(tr, all_dates):
    if len(tr)==0: return dict(sharpe=0,mdd=0,tot=0,cagr=0,win=0,n=0)
    dr=pd.Series(0.0,index=pd.to_datetime(all_dates)); dr.loc[tr["date"].values]=tr["ret"].values
    sh=dr.mean()/dr.std()*np.sqrt(252) if dr.std() else 0
    eq=(1+dr).cumprod(); mdd=((eq-eq.cummax())/eq.cummax()).min()*100
    yrs=(dr.index[-1]-dr.index[0]).days/365.25
    return dict(sharpe=sh,mdd=mdd,tot=(eq.iloc[-1]-1)*100,cagr=((eq.iloc[-1])**(1/yrs)-1)*100,
                win=(tr["ret"]>0).mean()*100,n=len(tr),eq=eq)

DATA="/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/fsdata/pyfinancialdata/data/currencies/oanda/NAS100_USD"
d,days=prep(DATA,2016,2020); ALL=list(d.index)
def show(tag,tr): m=metrics(tr,ALL); print(f"{tag:44} Sharpe {m['sharpe']:5.2f}  CAGR {m['cagr']:6.1f}%  MDD {m['mdd']:6.1f}%  win {m['win']:4.0f}%  n {m['n']}"); return m

print("=== OVERFIT MACHINE — NAS100 2016-2020 (IS, zero discipline) ===\n")
base=trades(d,days,20,25,60,571); show("0) baseline (your config: 20bps,g25,t60,9:31)",base)
# 1) greedy coordinate ascent
best=(20,25,60,571); bestS=metrics(base,ALL)["sharpe"]
for band in [10,12.5,15,17.5,20,22.5,25,27.5,30]:
    m=metrics(trades(d,days,band,best[1],best[2],best[3]),ALL)
    if m["sharpe"]>bestS: bestS=m["sharpe"]; best=(band,best[1],best[2],best[3])
for gp in [0,10,15,20,25,30,35,40,50]:
    m=metrics(trades(d,days,best[0],gp,best[2],best[3]),ALL)
    if m["sharpe"]>bestS: bestS=m["sharpe"]; best=(best[0],gp,best[2],best[3])
for tp in [40,50,55,60,65,70,80,90,100]:
    m=metrics(trades(d,days,best[0],best[1],tp,best[3]),ALL)
    if m["sharpe"]>bestS: bestS=m["sharpe"]; best=(best[0],best[1],tp,best[3])
for em in [571,575,585,595,600,615,630]:
    m=metrics(trades(d,days,best[0],best[1],best[2],em),ALL)
    if m["sharpe"]>bestS: bestS=m["sharpe"]; best=(best[0],best[1],best[2],em)
tr1=trades(d,days,*best); show(f"1) greedy-tuned params {best}",tr1)
# 2) hindsight: drop losing weekdays
tr2=tr1.copy(); tr2["wd"]=tr2["date"].dt.dayofweek
wdmean=tr2.groupby("wd")["ret"].mean(); goodwd=wdmean[wdmean>0].index
tr2=tr2[tr2["wd"].isin(goodwd)]; show(f"2) + drop losing weekdays {sorted(set(range(5))-set(goodwd))}",tr2)
# 3) hindsight: drop losing months-of-year
tr3=tr2.copy(); tr3["mo"]=tr3["date"].dt.month
momean=tr3.groupby("mo")["ret"].mean(); goodmo=momean[momean>0].index
tr3=tr3[tr3["mo"].isin(goodmo)]; show(f"3) + drop losing months {sorted(set(range(1,13))-set(goodmo))}",tr3)
# 4) hindsight: drop worst 15% of trading weeks
tr4=tr3.copy(); tr4["wk"]=tr4["date"].dt.isocalendar().week.astype(int)+tr4["date"].dt.year*100
wkmean=tr4.groupby("wk")["ret"].sum(); badwk=wkmean[wkmean<wkmean.quantile(0.15)].index
tr4=tr4[~tr4["wk"].isin(badwk)]; show("4) + drop worst 15% of weeks (cherry-pick)",tr4)
# 5) full cherry: drop worst 5% single trades
tr5=tr4.sort_values("ret"); tr5=tr5.iloc[int(len(tr5)*0.05):]; show("5) + delete worst 5% individual trades",tr5)
m=metrics(tr5,ALL)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig,ax=plt.subplots(figsize=(10,5))
for tag,tr,c in [("0 baseline (Sharpe 1.5)",base,"#999"),("1 tuned params",tr1,"#1f77b4"),("2 +drop weekdays",tr2,"#9467bd"),("3 +drop months",tr3,"#ff7f0e"),("5 +cherry-pick trades",tr5,"#d62728")]:
    mm=metrics(tr,ALL); ax.plot(mm["eq"].index,mm["eq"].values,label=f"{tag}: Sharpe {mm['sharpe']:.2f}",lw=1.4,color=c)
ax.set_yscale("log"); ax.set_title("OVERFIT MACHINE — same strategy, escalating curve-fit (NAS100 2016-2020, IS)\nFOR FUN — this is what fake looks like")
ax.set_ylabel("equity (log)"); ax.legend(fontsize=8); ax.grid(True,which="both",alpha=0.25)
fig.tight_layout(); fig.savefig("../results/vwap_overfit.png",dpi=130)
print("\nsaved vwap_overfit.png")
