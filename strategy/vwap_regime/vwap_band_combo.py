"""Replicate the user's VWAP hysteresis-band strategy; test fixed-bps band vs a
volatility-scaled band (k*sigma, the usable idea from Lee 2026 SSRN 6438039).
Vectorised VWAP/sigma; per-day numpy state machine. Unlevered per-trade returns."""
import sys, os, argparse
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orb_backtest import load_rth_1min, Config
OR31 = 9*60+31; EOD = 15*60+59

def prep(data_dir, s, e):
    df = load_rth_1min(Config(data_dir=data_dir, start_year=s, end_year=e)).copy()
    df = df.sort_values(["date","etmin"]).reset_index(drop=True)
    hlc3 = (df["high"]+df["low"]+df["close"])/3.0
    pv = hlc3*df["volume"]
    g = df.groupby("date", sort=True)
    cpv = g["__pv"].cumsum() if False else pv.groupby(df["date"]).cumsum()
    cv  = df["volume"].groupby(df["date"]).cumsum()
    cpv2 = (hlc3*hlc3*df["volume"]).groupby(df["date"]).cumsum()
    vwap = cpv/cv.replace(0,np.nan)
    df["vwap"] = vwap
    df["sd"] = np.sqrt(np.maximum(cpv2/cv.replace(0,np.nan) - vwap*vwap, 0.0))
    # daily table for gates
    rows=[]
    for date, gg in g:
        rows.append((date, gg["open"].iloc[0], gg["high"].max(), gg["low"].min(), gg["close"].iloc[-1]))
    d = pd.DataFrame(rows, columns=["date","o","h","l","c"]).set_index("date")
    d["prev_c"]=d["c"].shift(1); d["gap_bps"]=(d["o"]/d["prev_c"]-1).abs()*1e4
    d["trend"]=(d["c"]-d["o"]).abs()/(d["h"]-d["l"]).replace(0,np.nan); d["prev_trend"]=d["trend"].shift(1)
    # per-day slices (numpy)
    days={}
    for date, gg in g:
        days[date]=(gg["etmin"].to_numpy(), gg["close"].to_numpy(), gg["vwap"].to_numpy(), gg["sd"].to_numpy())
    return df, d, days

def run(d, days, band_mode, band_val, use_gap, use_trend, gap_pct=25.0, trend_pct=60.0, cost_bps=1.0, band_by_date=None):
    dates=list(d.index); gapH=[]; ptH=[]; day_ret={}; rets=[]
    for date in dates:
        row=d.loc[date]; gap=row["gap_bps"]; ytr=row["prev_trend"]
        def rk(h,v): return None if (v is None or (isinstance(v,float) and np.isnan(v)) or len(h)<60) else float(np.mean(np.array(h)<=v))
        gr=rk(gapH,gap); pr=rk(ptH,ytr)
        gapOK=(not use_gap) or gr is None or gr>=gap_pct/100.0
        ptOK =(not use_trend) or pr is None or pr<=trend_pct/100.0
        if not np.isnan(gap): gapH.append(gap); gapH[:]=gapH[-250:]
        if ytr is not None and not np.isnan(ytr): ptH.append(ytr); ptH[:]=ptH[-250:]
        if not (gapOK and ptOK) or date not in days: day_ret[date]=0.0; continue
        etm,cl,vw,sd=days[date]
        if band_mode=="bps":
            bb=band_by_date[date] if band_by_date is not None else band_val
            up=vw*(1+bb/1e4); dn=vw*(1-bb/1e4)
        else: up=vw+band_val*sd; dn=vw-band_val*sd
        pos=0; entry=0.0; traded=False; r=0.0
        for j in range(len(etm)):
            m=etm[j]
            if np.isnan(vw[j]): continue
            if m>=EOD:
                if pos!=0: r=pos*(cl[j]-entry)/entry; pos=0
                break
            if m<OR31: continue
            c=cl[j]
            if pos==0 and not traded:
                if c>up[j]: pos=1; entry=c; traded=True
                elif c<dn[j]: pos=-1; entry=c; traded=True
            elif pos==1 and c<dn[j]: r=(c-entry)/entry; pos=0
            elif pos==-1 and c>up[j]: r=-(c-entry)/entry; pos=0
        if traded: r-=2*cost_bps/1e4; rets.append(r)
        day_ret[date]=r if traded else 0.0
    dr=pd.Series(day_ret).reindex(dates).fillna(0.0); rets=np.array(rets)
    if len(rets)==0: return None
    sharpe=dr.mean()/dr.std()*np.sqrt(252) if dr.std() else 0
    eq=(1+dr).cumprod(); mdd=((eq-eq.cummax())/eq.cummax()).min()*100
    yrs=pd.Series(dr.values,index=pd.to_datetime(dr.index)).groupby(lambda x:x.year).apply(lambda s:((1+s).prod()-1)*100)
    return dict(n=len(rets),win=float((rets>0).mean()*100),avg_bps=float(rets.mean()*1e4),
                sharpe=float(sharpe),mdd=float(mdd),tot=float((eq.iloc[-1]-1)*100),
                yearly={int(k):round(v,1) for k,v in yrs.items()})

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",required=True)
    ap.add_argument("--start-year",type=int,default=2016); ap.add_argument("--end-year",type=int,default=2020)
    a=ap.parse_args()
    df,d,days=prep(a.data_dir,a.start_year,a.end_year)
    print(f"window {a.start_year}-{a.end_year}, {len(d)} days\n")
    cfgs=[("A fixed 20bps + gates",dict(band_mode="bps",band_val=20.0,use_gap=True,use_trend=True)),
          ("  fixed 20bps NO gates",dict(band_mode="bps",band_val=20.0,use_gap=False,use_trend=False)),
          ("B sigma k=1.0 + gates",dict(band_mode="sigma",band_val=1.0,use_gap=True,use_trend=True)),
          ("B sigma k=1.5 + gates",dict(band_mode="sigma",band_val=1.5,use_gap=True,use_trend=True)),
          ("B sigma k=2.0 + gates",dict(band_mode="sigma",band_val=2.0,use_gap=True,use_trend=True))]
    # day-vol-adaptive bps band (the 'smart' Lee combination): scale 20bps by
    # yesterday's 20d realised vol vs its median, clipped [0.6, 1.8]
    dret=d["c"].pct_change(); rv=dret.rolling(20).std().shift(1)
    med=rv.median(); scale=(rv/med).clip(0.6,1.8).fillna(1.0)
    band_by_date={dt:20.0*float(scale.loc[dt]) for dt in d.index}
    print(f"{'config':30} {'trades':>6} {'win%':>5} {'avgBps':>7} {'Sharpe':>7} {'MDD%':>7} {'tot%':>7}")
    res={}
    for name,kw in cfgs:
        r=run(d,days,**kw); res[name]=r
        if r: print(f"{name:30} {r['n']:>6} {r['win']:>5.0f} {r['avg_bps']:>7.1f} {r['sharpe']:>7.2f} {r['mdd']:>7.1f} {r['tot']:>7.0f}")
    rC=run(d,days,band_mode="bps",band_val=20.0,use_gap=True,use_trend=True,band_by_date=band_by_date)
    res["C day-vol-adaptive band + gates"]=rC
    if rC: print(f"{'C day-vol-adaptive + gates':30} {rC['n']:>6} {rC['win']:>5.0f} {rC['avg_bps']:>7.1f} {rC['sharpe']:>7.2f} {rC['mdd']:>7.1f} {rC['tot']:>7.0f}")
    print("\nper-year A(fixed) vs B(sigma k=1.5):")
    print("  A:", res["A fixed 20bps + gates"]["yearly"])
    print("  B:", res["B sigma k=1.5 + gates"]["yearly"])
