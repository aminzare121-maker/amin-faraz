//+------------------------------------------------------------------+
//| FARAZ M5 Read-Only Export - research only, NO trading operations   |
//| Exports M15 and M5 from same MT5 terminal and exact symbol.       |
//| Does NOT send orders, modify account settings or require Codex.   |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs
#property version "1.00"

input string InpSymbol = "XAUUSD.st";
input bool   InpQuickProbeOnly = true; // TRUE: two suspicious dates; FALSE: full 1y
input int    InpChunkDays = 3;         // Small requests / safe resume by re-run
input int    InpRetryCount = 3;

int file_m15 = INVALID_HANDLE;
int file_m5 = INVALID_HANDLE;
int file_log = INVALID_HANDLE;
string run_name = "";
int written_m15 = 0;
int written_m5 = 0;
int failed_chunks = 0;
int empty_chunks = 0;

void LogStatus(string message)
{
   Print("FARAZ_READ_ONLY: ", message);
   if(file_log != INVALID_HANDLE) FileWrite(file_log, message);
}

bool ExportRange(ENUM_TIMEFRAMES timeframe, datetime from_time, datetime to_time, int handle)
{
   int chunk_days = MathMax(1, MathMin(31, InpChunkDays));
   int retry_count = MathMax(1, MathMin(6, InpRetryCount));
   datetime current_time = from_time;
   bool all_ok = true;
   while(current_time <= to_time && !IsStopped())
   {
      datetime last_time = current_time + chunk_days * 86400 - 1;
      if(last_time > to_time) last_time = to_time;
      MqlRates bars[];
      int count = -1;
      int last_error = 0;
      for(int attempt=0; attempt<retry_count; attempt++)
      {
         ResetLastError();
         count = CopyRates(InpSymbol, timeframe, current_time, last_time, bars);
         last_error = GetLastError();
         if(count >= 0) break;
         Sleep(1200);
      }
      if(count < 0)
      {
         failed_chunks++;
         all_ok = false;
         LogStatus(StringFormat("FAILED period=%d from=%s to=%s MT5_error=%d (NOT evidence of no market candles)",
                     (int)timeframe, TimeToString(current_time, TIME_DATE|TIME_SECONDS),
                     TimeToString(last_time,TIME_DATE|TIME_SECONDS),last_error));
      }
      else if(count == 0)
      {
         empty_chunks++;
         LogStatus(StringFormat("EMPTY period=%d from=%s to=%s (market closure OR unavailable history; UNKNOWN)",
                     (int)timeframe, TimeToString(current_time,TIME_DATE|TIME_SECONDS),
                     TimeToString(last_time,TIME_DATE|TIME_SECONDS)));
      }
      else
      {
         int period_seconds = PeriodSeconds(timeframe);
         datetime last_closed = TimeCurrent();
         int written_now = 0;
         for(int i=0;i<count;i++)
         {
            // Only completed historical candles, never the still-open candle
            if(bars[i].time + period_seconds > last_closed) continue;
            if(bars[i].time < current_time || bars[i].time > last_time) continue;
            FileWrite(handle,
               TimeToString(bars[i].time,TIME_DATE|TIME_SECONDS),
               InpSymbol,
               DoubleToString(bars[i].open,8),
               DoubleToString(bars[i].high,8),
               DoubleToString(bars[i].low,8),
               DoubleToString(bars[i].close,8),
               (string)bars[i].tick_volume,
               (string)bars[i].spread);
            written_now++;
         }
         if(timeframe==PERIOD_M5) written_m5 += written_now;
         else written_m15 += written_now;
         LogStatus(StringFormat("OK period=%d from=%s copied=%d written_closed=%d",
                   (int)timeframe,TimeToString(current_time,TIME_DATE|TIME_SECONDS),count,written_now));
      }
      current_time = last_time + 1;
   }
   return all_ok && !IsStopped();
}


// Quick on-screen result: works even without Python. A found M5 bar is only
// evidence about the CURRENT terminal export, not a verified prior M15 bar.
void ProbeOne(int gap_id, string target_label)
{
   datetime target=StringToTime(target_label);
   MqlRates quarter[];
   MqlRates fifths[];
   ResetLastError();
   int qcount=CopyRates(InpSymbol,PERIOD_M15,target,target,quarter);
   int qerror=GetLastError();
   ResetLastError();
   int fcount=CopyRates(InpSymbol,PERIOD_M5,target,target+600,fifths);
   int ferror=GetLastError();
   bool has_m15=false;
   for(int i=0;i<qcount;i++) if(quarter[i].time==target) has_m15=true;
   bool present[3]={false,false,false};
   double opens[3], highs[3], lows[3], closes[3];
   for(int i=0;i<fcount;i++)
   {
      long offset=(long)(fifths[i].time-target);
      if(offset==0 || offset==300 || offset==600)
      {
         int idx=(int)(offset/300);
         present[idx]=true;
         opens[idx]=fifths[i].open;
         highs[idx]=fifths[i].high;
         lows[idx]=fifths[i].low;
         closes[idx]=fifths[i].close;
      }
   }
   int have=(int)present[0]+(int)present[1]+(int)present[2];
   string status=(have==3?"THREE_M5_FOUND_UNVERIFIED":(have>0?"PARTIAL_M5":"M5_UNKNOWN_NOT_FOUND"));
   LogStatus(StringFormat("PROBE gap=%d t=%s M15_return=%d M15_time_present=%s M15_error=%d M5_return=%d M5_exact=%d/3 M5_error=%d status=%s",
         gap_id,target_label,qcount,has_m15?"YES":"NO_OR_UNAVAILABLE",qerror,fcount,have,ferror,status));
   if(have==3)
   {
      double high=MathMax(highs[0],MathMax(highs[1],highs[2]));
      double low=MathMin(lows[0],MathMin(lows[1],lows[2]));
      LogStatus(StringFormat("PROBE_CANDIDATE gap=%d open=%.5f high=%.5f low=%.5f close=%.5f; NOT verified against 100 other M15 bars; never fill original raw",
               gap_id,opens[0],high,low,closes[2]));
   }
}

void OnStart()
{
   // Fail closed before creating outputs or requesting broker history.
   string broker=AccountInfoString(ACCOUNT_COMPANY);
   StringToLower(broker);
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO ||
      StringFind(broker,"eplanet")<0 || InpSymbol!="XAUUSD.st")
   {
      Print("FARAZ_ABORT: requires Eplanet DEMO and exact XAUUSD.st. No requests made.");
      return;
   }
   if(FileIsExist("FARAZ_probe_M15.csv",FILE_COMMON) ||
      FileIsExist("FARAZ_probe_M5.csv",FILE_COMMON) ||
      FileIsExist("FARAZ_probe_export_log.txt",FILE_COMMON))
   {
      Print("FARAZ_ABORT: archive prior Common Files outputs privately before a new run.");
      return;
   }
   if(SymbolInfoInteger(InpSymbol,SYMBOL_SELECT)==0)
   {
      Print("FARAZ_ABORT: exact symbol is not already selected in Market Watch: ",InpSymbol,". No symbol/settings modified.");
      return;
   }
   run_name = "FARAZ_M5_READONLY_" + TimeToString(TimeLocal(),TIME_DATE|TIME_MINUTES);
   StringReplace(run_name,".","-");
   StringReplace(run_name,":","-");
   StringReplace(run_name," ","_");

   file_m15 = FileOpen("FARAZ_probe_M15.csv",FILE_COMMON|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   file_m5 = FileOpen("FARAZ_probe_M5.csv",FILE_COMMON|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   file_log = FileOpen("FARAZ_probe_export_log.txt",FILE_COMMON|FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(file_m15==INVALID_HANDLE || file_m5==INVALID_HANDLE || file_log==INVALID_HANDLE)
   {
      Print("FARAZ_ABORT: cannot create Common Files outputs, error=",GetLastError());
      if(file_m15!=INVALID_HANDLE) FileClose(file_m15);
      if(file_m5!=INVALID_HANDLE) FileClose(file_m5);
      if(file_log!=INVALID_HANDLE) FileClose(file_log);
      return;
   }
   FileWrite(file_m15,"time","symbol","open","high","low","close","tick_volume","spread");
   FileWrite(file_m5,"time","symbol","open","high","low","close","tick_volume","spread");
   LogStatus("RUN="+run_name+"; SYMBOL="+InpSymbol+"; READ_ONLY; 5m/15m; NO ORDERS;");
   LogStatus("Clock labels are MT5 chart timestamps; relation to prior Python raw epochs is unverified.");
   LogStatus("MT5 max-bars/history availability can cause failures. Do not treat them as broker manipulation.");
   datetime from_times[2];
   datetime to_times[2];
   int range_count = 0;
   if(InpQuickProbeOnly)
   {
      from_times[0] = StringToTime("2025.11.27 00:00:00");
      to_times[0]   = StringToTime("2025.11.29 23:59:59");
      from_times[1] = StringToTime("2026.05.24 00:00:00");
      to_times[1]   = StringToTime("2026.05.27 23:59:59");
      range_count = 2;
      LogStatus("QUICK PROBE: 2025-11-28 11:00 and 2026-05-25 22:00 (prior CSV labels)");
   }
   else
   {
      from_times[0] = StringToTime("2025.11.05 00:00:00");
      to_times[0]   = StringToTime("2026.11.05 23:59:59");
      range_count = 1;
      LogStatus("FULL-YEAR QUERY; M5 may exceed Max bars in chart: failures are NOT proof of missing quotes");
   }
   bool complete = true;
   for(int j=0;j<range_count;j++)
   {
      if(!ExportRange(PERIOD_M15,from_times[j],to_times[j],file_m15)) complete = false;
      if(!ExportRange(PERIOD_M5,from_times[j],to_times[j],file_m5)) complete = false;
   }
   FileFlush(file_m15); FileFlush(file_m5);
   ProbeOne(18,"2025.11.28 11:00:00");
   ProbeOne(142,"2026.05.25 22:00:00");
   LogStatus(StringFormat("END complete=%s M15_bars=%d M5_bars=%d failed_chunks=%d empty_chunks=%d",
             complete?"true":"false",written_m15,written_m5,failed_chunks,empty_chunks));
   LogStatus("Local Common Files outputs: FARAZ_probe_M15.csv and FARAZ_probe_M5.csv");
   FileClose(file_m15); FileClose(file_m5); FileClose(file_log);
}
