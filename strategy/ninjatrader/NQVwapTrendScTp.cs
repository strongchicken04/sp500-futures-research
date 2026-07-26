#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Strategies;
#endregion

// =====================================================================
// NQ VWAP Trend — Strong Chicken AUTO, verze TP/SL (NinjaTrader 8, v1)
// Stejná finální logika jako NQVwapTrendSC (session VWAP RTH, pásmo ±20 bps,
// gap gate 25 + trend gate 60, vstup od 9:31, 1 obchod/den, band exit + EOD),
// ale s PEVNÝM BRACKETEM: TP +100 bodů, SL −75 bodů (resting u brokera).
//
// Čísla z mřížky na reálném NQ 2018–2025 (finální konfigurace, 1 bp/side):
//   TP100+SL75: avg 9,31 b/obchod, win 42 %, Sharpe 1,02, tot +59 %, MDD −5,2 %
//   vs bez TP:  avg 12,99 b,       win 39 %, Sharpe 1,23, tot +105 %, MDD −7,0 %
// -> TP verze vydělává MÉNĚ, ale má hladší křivku a nižší drawdown; na prop
//    challenge s trailing DD může být operačně rozumná volba. Pozn.: přínos
//    SL75 vs bez SL byl v bootstrapu v pásmu šumu (90% CI [−0,04; +0,16]).
// POZOR: TP i SL v bodech, kalibrace na éře 2018–2025 — revidovat s růstem NQ.
//
// POUŽITÍ: shodné s NQVwapTrendSC (1m graf NQ/MNQ, Trading hours "US Equities
// RTH", Days to load >= 450, nejdřív Sim101). Viz README.
// =====================================================================
namespace NinjaTrader.NinjaScript.Strategies
{
    public class NQVwapTrendScTp : Strategy
    {
        private double cumPV, cumV, vwapVal;
        private readonly List<double> gapHist = new List<double>();
        private readonly List<double> ptHist  = new List<double>();
        private double prevSessClose = double.NaN;
        private double dOpen = double.NaN, dHi = double.NaN, dLo = double.NaN;
        private bool allowedToday = true;
        private bool tradedToday  = false;
        private string gateReason = "";

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description  = "VWAP pasmo 20bps + gaty, 1 obchod/den, fixni TP 100 b / SL 75 b, band exit + EOD.";
                Name         = "NQVwapTrendScTp";
                Calculate    = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds    = 30;
                BarsRequiredToTrade = 30;
                StartBehavior = StartBehavior.WaitUntilFlat;
                Slippage = 1;

                BandBps      = 20.0;
                UseGapGate   = true;
                GapPct       = 25.0;
                UseTrendGate = true;
                TrendPct     = 60.0;
                TpPoints     = 100.0;
                SlPoints     = 75.0;
                UseBandExit  = true;
                Contracts    = 1;
            }
            else if (State == State.DataLoaded)
            {
                if (SlPoints > 0)
                    SetStopLoss(CalculationMode.Ticks, Math.Max(1, (int)Math.Round(SlPoints / TickSize)));
                if (TpPoints > 0)
                    SetProfitTarget(CalculationMode.Ticks, Math.Max(1, (int)Math.Round(TpPoints / TickSize)));
            }
        }

        private static double Rank(List<double> hist, double val)
        {
            if (hist.Count < 60 || double.IsNaN(val)) return double.NaN;
            int below = 0;
            foreach (double x in hist) if (x <= val) below++;
            return 100.0 * below / hist.Count;
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0 || CurrentBar < 1) return;

            // ---------- nový RTH den: gaty (past-only), reset ----------
            if (Bars.IsFirstBarOfSession)
            {
                double yTrend = double.NaN;
                if (!double.IsNaN(dOpen) && !double.IsNaN(dHi) && !double.IsNaN(dLo)
                    && !double.IsNaN(prevSessClose) && dHi > dLo)
                    yTrend = Math.Abs(prevSessClose - dOpen) / (dHi - dLo);

                double gap = double.NaN;
                if (!double.IsNaN(prevSessClose) && prevSessClose > 0)
                    gap = Math.Abs(Open[0] / prevSessClose - 1.0) * 10000.0;

                double gapRank = Rank(gapHist, gap);
                double ptRank  = Rank(ptHist,  yTrend);
                bool gapOK = !UseGapGate   || double.IsNaN(gapRank) || gapRank >= GapPct;
                bool ptOK  = !UseTrendGate || double.IsNaN(ptRank)  || ptRank  <= TrendPct;
                allowedToday = gapOK && ptOK;
                gateReason = (!gapOK && !ptOK) ? "gap+trend" : !gapOK ? "gap" : !ptOK ? "trend" : "";

                if (!double.IsNaN(gap))    { gapHist.Add(gap);   if (gapHist.Count > 250) gapHist.RemoveAt(0); }
                if (!double.IsNaN(yTrend)) { ptHist.Add(yTrend); if (ptHist.Count  > 250) ptHist.RemoveAt(0); }

                cumPV = 0.0; cumV = 0.0;
                tradedToday = false;
                dOpen = Open[0]; dHi = High[0]; dLo = Low[0];

                if (State == State.Realtime)
                    Print(string.Format("{0}  VWAPTrend TP/SL: {1}", Time[0].Date.ToShortDateString(),
                        allowedToday ? "OBCHODNI DEN" : "NO TRADE DAY (" + gateReason + ")"));
            }

            // ---------- akumulace dne ----------
            dHi = Math.Max(double.IsNaN(dHi) ? High[0] : dHi, High[0]);
            dLo = Math.Min(double.IsNaN(dLo) ? Low[0]  : dLo, Low[0]);
            prevSessClose = Close[0];

            double hlc3 = (High[0] + Low[0] + Close[0]) / 3.0;
            cumPV += hlc3 * Volume[0];
            cumV  += Volume[0];
            if (cumV <= 0) return;
            vwapVal = cumPV / cumV;

            double b  = BandBps / 10000.0;
            double up = vwapVal * (1 + b);
            double dn = vwapVal * (1 - b);

            int t = ToTime(Time[0]);

            // ---------- EOD flat ----------
            if (t >= 155900)
            {
                if (Position.MarketPosition == MarketPosition.Long)  ExitLong("EOD", "L");
                if (Position.MarketPosition == MarketPosition.Short) ExitShort("EOD", "S");
                return;
            }

            // ---------- vstup / band exit (TP+SL drží broker přes bracket) ----------
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                if (!tradedToday && allowedToday && t >= 93200)
                {
                    if (Close[0] > up)      { EnterLong(Contracts, "L");  tradedToday = true; }
                    else if (Close[0] < dn) { EnterShort(Contracts, "S"); tradedToday = true; }
                }
            }
            else if (UseBandExit && Position.MarketPosition == MarketPosition.Long  && Close[0] < dn)
                ExitLong("BandExit", "L");
            else if (UseBandExit && Position.MarketPosition == MarketPosition.Short && Close[0] > up)
                ExitShort("BandExit", "S");
        }

        #region Properties
        [NinjaScriptProperty, Range(0, double.MaxValue)]
        [Display(Name = "Pasmo (bps)", Order = 1, GroupName = "Strategie")]
        public double BandBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Gap gate", Order = 2, GroupName = "Strategie")]
        public bool UseGapGate { get; set; }

        [NinjaScriptProperty, Range(0, 90)]
        [Display(Name = "Gap gate percentil", Order = 3, GroupName = "Strategie")]
        public double GapPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trend gate", Order = 4, GroupName = "Strategie")]
        public bool UseTrendGate { get; set; }

        [NinjaScriptProperty, Range(10, 95)]
        [Display(Name = "Trend gate percentil", Order = 5, GroupName = "Strategie")]
        public double TrendPct { get; set; }

        [NinjaScriptProperty, Range(0, double.MaxValue)]
        [Display(Name = "TP (body)", Order = 6, GroupName = "Strategie")]
        public double TpPoints { get; set; }

        [NinjaScriptProperty, Range(0, double.MaxValue)]
        [Display(Name = "SL (body)", Order = 7, GroupName = "Strategie")]
        public double SlPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Band exit ponechat", Order = 8, GroupName = "Strategie")]
        public bool UseBandExit { get; set; }

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "Kontrakty", Order = 9, GroupName = "Strategie")]
        public int Contracts { get; set; }
        #endregion
    }
}
