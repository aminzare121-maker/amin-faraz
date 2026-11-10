//+------------------------------------------------------------------+
//| Artin V13 — CLOSED M15 DATA COLLECTOR ONLY (no trading code)      |
//| Build status: source drafted; compile/run requires MetaEditor MT5 |
//| Broker clock is preserved without asserting a UTC offset.        |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"
#property description "Artin V13 / Eplanet XAUUSD M15 DEMO-only CLOSED-bar CSV collector"
#property description "NO signals. NO orders. NO external network. NO trade library."

input int InpPollSeconds=5;
string g_filename="artin_v13_demo_m15_closed_bars.csv";
string g_clock_key="";
datetime g_last_bar=0;

bool ConfirmSafety()
  {
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     { Print("ARTIN BLOCKED: DEMO account mandatory"); return false; }
   if(StringFind(_Symbol,"XAUUSD",0)!=0)
     { Print("ARTIN BLOCKED: XAUUSD symbol required"); return false; }
   if(_Period!=PERIOD_M15)
     { Print("ARTIN BLOCKED: M15 chart required"); return false; }
   return true;
  }

int OnInit()
  {
   if(!ConfirmSafety()) return INIT_FAILED;
   if(InpPollSeconds<1 || InpPollSeconds>60) return INIT_PARAMETERS_INCORRECT;
   g_clock_key="ArtinV13.shadow."+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))
               +"."+_Symbol+".M15";
   if(GlobalVariableCheck(g_clock_key))
     g_last_bar=(datetime)(long)GlobalVariableGet(g_clock_key);
   // Build an append-only file in the terminal COMMON Files directory.
   int h=FileOpen(g_filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,',');
   if(h==INVALID_HANDLE)
     { Print("ARTIN BLOCKED: cannot open CSV, error ",GetLastError()); return INIT_FAILED; }
   if(FileSize(h)==0)
     FileWrite(h,"source_label","broker_epoch","broker_walltime","symbol","timeframe",
               "open","high","low","close","tick_volume","spread","real_volume",
               "teacher_semantics_verified","trade_authorized");
   FileFlush(h);
   FileClose(h);
   EventSetTimer(InpPollSeconds);
   Print("ARTIN V13: READ-ONLY DEMO shadow collector active. Orders intentionally impossible.");
   return INIT_SUCCEEDED;
  }

void OnTimer()
  {
   if(!ConfirmSafety()) { EventKillTimer(); return; }
   MqlRates rates[];
   // Position 1 = most recent FULLY CLOSED M15 bar; never use forming bar 0.
   if(CopyRates(_Symbol,PERIOD_M15,1,1,rates)!=1) return;
   MqlRates r=rates[0];
   if(r.time<=g_last_bar) return;
   if(((long)r.time)%900!=0) { Print("ARTIN BLOCKED: off-grid M15 time"); return; }
   if(r.low<=0 || r.high<r.low || r.open<r.low || r.open>r.high
      || r.close<r.low || r.close>r.high) return;
   int h=FileOpen(g_filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,',');
   if(h==INVALID_HANDLE) { Print("ARTIN FILE ERROR ",GetLastError()); return; }
   FileSeek(h,0,SEEK_END);
   FileWrite(h,"MT5_TERMINAL_DEMO_CLOSED_BAR_RAW_BROKER_CLOCK",
             IntegerToString((long)r.time),TimeToString(r.time,TIME_DATE|TIME_SECONDS),
             _Symbol,"M15",DoubleToString(r.open,_Digits),DoubleToString(r.high,_Digits),
             DoubleToString(r.low,_Digits),DoubleToString(r.close,_Digits),
             IntegerToString((long)r.tick_volume),IntegerToString(r.spread),
             IntegerToString((long)r.real_volume),"0","0");
   FileFlush(h);FileClose(h);
   g_last_bar=r.time;
   GlobalVariableSet(g_clock_key,(double)g_last_bar);
  }

void OnDeinit(const int reason) { EventKillTimer(); }
void OnTick() { /* No trading and no new-bar events: timer only */ }