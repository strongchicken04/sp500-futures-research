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
// NQ VWAP Trend — Strong Chicken AUTO (NinjaTrader 8 port, v1)
// Finální konfigurace z výzkumu (IS 2018–2025, out-of-era validace 2005–2017,
// PASS z optimalizační mašiny):
//   * session VWAP (RTH, HLC3), hysterezní pásmo ±20 bps
//   * vstup od 9:31 (close 1m svíčky za pásmem), 1 obchod/den
//   * exit: close za opačným pásmem, nebo 15:59 ET (flat před 16:00)
//   * GAP GATE: neobchoduj, když |overnight gap| < 25. percentil 250 dní
//   * TREND GATE: neobchoduj den po silně trendovém dni (>60. percentil)
//   * FIXNÍ SL 150 b (katastrofická pojistka — dle SL mřížky na reálném NQ
//     2018–2025 má nulovou historickou cenu; resting stop u brokera chrání
//     i při výpadku spojení)
//
// POUŽITÍ (Lucid Trading / Rithmic):
//   1. Graf: NQ nebo MNQ, 1 minuta, Trading hours = "US Equities RTH"
//      (09:30–16:00 ET), Days to load >= 450 (kvůli warm-upu bran).
//   2. Strategies -> přidat NQVwapTrendSC, účet = Lucid (Rithmic) připojení.
//   3. Nejdřív týden na Sim101 / Market Replay a porovnat signály s TV v7!
//   Gaty se při zapnutí strategie samy dopočítají z historických barů grafu
//   (plná věrnost od ~250 RTH dní historie, aktivní od 60).
// Sizing: fixní počet kontraktů (VT15 řeš na úrovni účtu / velikosti).
// =====================================================================
namespace NinjaTrader.NinjaScript.Strategies
{
    public class NQVwapTrendSC : Strategy
    {
        private double cumPV, cumV, vwapVal;
        private readonly List<double> gapHist = new List<double>();
        private readonly List<double> ptHist  = new List<double>();
        private double prevSessClose = double.NaN;   // včerejší 16:00 RTH close
        private double dOpen = double.NaN, dHi = double.NaN, dLo = double.NaN;
        private bool allowedToday = true;
        private bool tradedToday  = false;
        private string gateReason = "";

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description  = "VWAP hysterezni pasmo 20bps + gap/trend gate, 1 obchod/den, exit opacne pasmo/EOD, fixni SL.";
                Name         = "NQVwapTrendSC";
                Calculate    = Calculate.OnBarClose;          // rozhodnutí na close 1m svíčky
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;          // pojistka platformy
                ExitOnSessionCloseSeconds    = 30;
                BarsRequiredToTrade = 30;
                StartBehavior = StartBehavior.WaitUntilFlat;
                Slippage = 1;

                BandBps      = 20.0;
                UseGapGate   = true;
                GapPct       = 25.0;
                UseTrendGate = true;
                TrendPct     = 60.0;
                UseFixedSL   = true;
                SlPoints     = 150.0;
                Contracts    = 1;
            }
            else if (State == State.DataLoaded)
            {
                if (UseFixedSL && SlPoints > 0)
                    SetStopLoss(CalculationMode.Ticks, Math.Max(1, (int)Math.Round(SlPoints / TickSize)));
            }
        }

        private static double Rank(List<double> hist, double val)
        {
            // percentil (0..100) hodnoty vůči MINULÝM dnům; NaN dokud < 60 dní historie
            if (hist.Count < 60 || double.IsNaN(val)) return double.NaN;
            int below = 0;
            foreach (double x in hist) if (x <= val) below++;
            return 100.0 * below / hist.Count;
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0 || CurrentBar < 1) return;

            // ---------- nový RTH den: gaty (past-only), reset akumulátorů ----------
            if (Bars.IsFirstBarOfSession)
            {
                // trendovost VČEREJŠKA z dokončeného RTH dne
                double yTrend = double.NaN;
                if (!double.IsNaN(dOpen) && !double.IsNaN(dHi) && !double.IsNaN(dLo)
                    && !double.IsNaN(prevSessClose) && dHi > dLo)
                    yTrend = Math.Abs(prevSessClose - dOpen) / (dHi - dLo);

                // dnešní |gap|: 9:30 open (Open[0] první svíčky) vs včerejší 16:00 close
                double gap = double.NaN;
                if (!double.IsNaN(prevSessClose) && prevSessClose > 0)
                    gap = Math.Abs(Open[0] / prevSessClose - 1.0) * 10000.0;

                // ranky proti historii (historie bez dneška/včerejška -> žádný lookahead)
                double gapRank = Rank(gapHist, gap);
                double ptRank  = Rank(ptHist,  yTrend);
                bool gapOK = !UseGapGate   || double.IsNaN(gapRank) || gapRank >= GapPct;
                bool ptOK  = !UseTrendGate || double.IsNaN(ptRank)  || ptRank  <= TrendPct;
                allowedToday = gapOK && ptOK;
                gateReason = (!gapOK && !ptOK) ? "gap+trend" : !gapOK ? "gap" : !ptOK ? "trend" : "";

                // AŽ TEĎ do historie (po výpočtu ranků), okno 250
                if (!double.IsNaN(gap))    { gapHist.Add(gap);    if (gapHist.Count > 250) gapHist.RemoveAt(0); }
                if (!double.IsNaN(yTrend)) { ptHist.Add(yTrend);  if (ptHist.Count  > 250) ptHist.RemoveAt(0); }

                // reset dne
                cumPV = 0.0; cumV = 0.0;
                tradedToday = false;
                dOpen = Open[0]; dHi = High[0]; dLo = Low[0];

                if (State == State.Realtime)
                    Print(string.Format("{0}  VWAPTrend: {1}", Time[0].Date.ToShortDateString(),
                        allowedToday ? "OBCHODNI DEN" : "NO TRADE DAY (" + gateReason + ")"));
            }

            // ---------- akumulace dne ----------
            dHi = Math.Max(double.IsNaN(dHi) ? High[0] : dHi, High[0]);
            dLo = Math.Min(double.IsNaN(dLo) ? Low[0]  : dLo, Low[0]);
            prevSessClose = Close[0];                    // po posledním baru dne = 16:00 close

            double hlc3 = (High[0] + Low[0] + Close[0]) / 3.0;
            cumPV += hlc3 * Volume[0];
            cumV  += Volume[0];
            if (cumV <= 0) return;
            vwapVal = cumPV / cumV;

            double b  = BandBps / 10000.0;
            double up = vwapVal * (1 + b);
            double dn = vwapVal * (1 - b);

            int t = ToTime(Time[0]);                     // čas KONCE svíčky (NT8 stampuje koncem)

            // ---------- EOD flat (close 15:58–59 svíčky -> flat před 16:00) ----------
            if (t >= 155900)
            {
                if (Position.MarketPosition == MarketPosition.Long)  ExitLong("EOD", "L");
                if (Position.MarketPosition == MarketPosition.Short) ExitShort("EOD", "S");
                return;
            }

            // ---------- vstup (od close 9:31 svíčky = stamp 9:32) / band exit ----------
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                if (!tradedToday && allowedToday && t >= 93200)
                {
                    if (Close[0] > up)      { EnterLong(Contracts, "L");  tradedToday = true; }
                    else if (Close[0] < dn) { EnterShort(Contracts, "S"); tradedToday = true; }
                }
            }
            else if (Position.MarketPosition == MarketPosition.Long  && Close[0] < dn)
                ExitLong("BandExit", "L");
            else if (Position.MarketPosition == MarketPosition.Short && Close[0] > up)
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

        [NinjaScriptProperty]
        [Display(Name = "Fixni SL (pojistka)", Order = 6, GroupName = "Strategie")]
        public bool UseFixedSL { get; set; }

        [NinjaScriptProperty, Range(0, double.MaxValue)]
        [Display(Name = "SL (body)", Order = 7, GroupName = "Strategie")]
        public double SlPoints { get; set; }

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "Kontrakty", Order = 8, GroupName = "Strategie")]
        public int Contracts { get; set; }
        #endregion
    }
}
