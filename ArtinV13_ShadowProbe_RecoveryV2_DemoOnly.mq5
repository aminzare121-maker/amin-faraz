//+------------------------------------------------------------------+
//| Artin V13: DEMO M15 read-only collector, recovery revision V2    |
//| Source only: COMPILE IN METAEDITOR NOT YET VERIFIED. NO TRADING.  |
//+------------------------------------------------------------------+
#property strict
#property version "2.00"
#property description "Artin V13 DEMO M15 CSV recovery probe; NO signals/orders/network"

input int InpPollSeconds=5;
input int InpInitialClosedBars=96; // new CSV: backfill this many closed bars
input int InpBatchBars=256;         // repair old missed bars chronologically
input int InpMaxCatchupBars=5000;   // block when history is too old to prove

const string SOURCE="MT5_TERMINAL_DEMO_CLOSED_BAR_RAW_BROKER_CLOCK";
const string HEADER[14]={"source_label","broker_epoch","broker_walltime","symbol","timeframe",
                         "open","high","low","close","tick_volume","spread","real_volume",
                         "teacher_semantics_verified","trade_authorized"};
int g_file=INVALID_HANDLE;
string g_filename="";
datetime g_last_bar=0;
bool g_halted=false;

bool SafeAccountChart()
  {
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     { Print("ARTIN V2 BLOCKED: account must be DEMO");return false; }
   if(StringFind(_Symbol,"XAUUSD",0)!=0)
     { Print("ARTIN V2 BLOCKED: symbol must start with XAUUSD");return false; }
   if(_Period!=PERIOD_M15)
     { Print("ARTIN V2 BLOCKED: chart must be M15");return false; }
   return true;
  }

string SafeFilenameToken(const string value)
  {
   string out="";
   for(int i=0;i<StringLen(value);i++)
     {
      ushort x=StringGetCharacter(value,i);
      if((x>=65 && x<=90)||(x>=97 && x<=122)||(x>=48 && x<=57)
         ||x==95||x==45||x==46)out+=ShortToString(x);
      else out+="_";
     }
   return out;
  }

bool DigitsOnly(const string s)
  {
   if(StringLen(s)==0)return false;
   for(int i=0;i<StringLen(s);i++)
     {
      ushort d=StringGetCharacter(s,i);
      if(d<48||d>57)return false;
     }
   return true;
  }

bool ValidDecimalCell(const string s)
  {
   if(StringLen(s)==0)return false;
   int dots=0;
   for(int i=0;i<StringLen(s);i++)
     {
      ushort d=StringGetCharacter(s,i);
      if(d==46){dots++;if(dots>1)return false;}
      else if(d<48||d>57)return false;
     }
   return true;
  }

// Preserve rows exactly as written. CSV is the sole restart checkpoint: never
// trust a global MT5 variable that might outlive a deleted or truncated CSV.
bool ReadLastCommittedBar()
  {
   g_last_bar=0;
   FileSeek(g_file,0,SEEK_SET);
   if(FileSize(g_file)==0)
     {
      FileWrite(g_file,"source_label","broker_epoch","broker_walltime","symbol","timeframe",
                "open","high","low","close","tick_volume","spread","real_volume",
                "teacher_semantics_verified","trade_authorized");
      FileFlush(g_file);
      FileSeek(g_file,0,SEEK_END);
      return true;
     }
   for(int i=0;i<14;i++)
     {
      if(FileIsEnding(g_file)||FileReadString(g_file)!=HEADER[i])
        { Print("ARTIN V2 BLOCKED: existing CSV header not recognized");return false; }
     }
   int lines=0;
   while(!FileIsEnding(g_file))
     {
      string row[14];
      for(int j=0;j<14;j++)
        {
         if(FileIsEnding(g_file))
           { Print("ARTIN V2 BLOCKED: incomplete historical row ",lines+1);return false; }
         row[j]=FileReadString(g_file);
        }
      if(row[0]!=SOURCE||row[3]!=_Symbol||row[4]!="M15"||row[12]!="0"||row[13]!="0")
        { Print("ARTIN V2 BLOCKED: wrong source or authorization flag at row ",lines+1);return false; }
      string time_text=row[1];
      if(StringLen(time_text)<9||StringLen(time_text)>12)
        { Print("ARTIN V2 BLOCKED: invalid timestamp width");return false; }
      if(!DigitsOnly(time_text))
        { Print("ARTIN V2 BLOCKED: invalid timestamp digit");return false; }
      datetime current=(datetime)StringToInteger(time_text);
      if(current<=g_last_bar||((long)current)%900!=0)
        { Print("ARTIN V2 BLOCKED: CSV duplicate, reversed or off-grid bar");return false; }
      if(row[2]!=TimeToString(current,TIME_DATE|TIME_SECONDS))
        { Print("ARTIN V2 BLOCKED: CSV timestamp and wallclock mismatch");return false; }
      double price[4];
      for(int p=5;p<=8;p++)
        {
         if(!ValidDecimalCell(row[p]))
           { Print("ARTIN V2 BLOCKED: malformed historical price");return false; }
         price[p-5]=StringToDouble(row[p]);
         if(!MathIsValidNumber(price[p-5])||price[p-5]<=0)
           { Print("ARTIN V2 BLOCKED: invalid historical price");return false; }
        }
      double op=price[0],hi=price[1],lo=price[2],cl=price[3];
      if(lo>MathMin(op,cl)||hi<MathMax(op,cl)||hi<lo)
        { Print("ARTIN V2 BLOCKED: corrupt OHLC in persisted CSV");return false; }
      for(int v=9;v<=11;v++)
        {
         if(!DigitsOnly(row[v]))
           { Print("ARTIN V2 BLOCKED: invalid volume or spread");return false; }
        }
      g_last_bar=current;
      lines++;
      if(lines>500000){ Print("ARTIN V2 BLOCKED: unusually large CSV");return false; }
     }
   FileFlush(g_file); // mandatory synchronization between reads and writes
   FileSeek(g_file,0,SEEK_END);
   Print("ARTIN V2: CSV recovered; stored closed bars=",lines,
         ", last broker clock=",TimeToString(g_last_bar,TIME_DATE|TIME_SECONDS));
   return true;
  }

bool AppendClosedBar(const MqlRates &r)
  {
   if(r.time<=g_last_bar || ((long)r.time)%900!=0)
     { Print("ARTIN V2 BLOCKED: overlapping or off-grid bar");return false; }
   if(!MathIsValidNumber(r.open)||!MathIsValidNumber(r.high)
      ||!MathIsValidNumber(r.low)||!MathIsValidNumber(r.close)
      ||r.low<=0||r.high<r.low||r.open<r.low||r.open>r.high
      ||r.close<r.low||r.close>r.high||r.tick_volume<0
      ||r.spread<0||r.real_volume<0)
     { Print("ARTIN V2 BLOCKED: invalid OHLC or volume");return false; }
   if(g_file==INVALID_HANDLE || !SafeAccountChart())return false;
   FileSeek(g_file,0,SEEK_END);
   uint written=FileWrite(g_file,SOURCE,
                         IntegerToString((long)r.time),TimeToString(r.time,TIME_DATE|TIME_SECONDS),
                         _Symbol,"M15",DoubleToString(r.open,_Digits),DoubleToString(r.high,_Digits),
                         DoubleToString(r.low,_Digits),DoubleToString(r.close,_Digits),
                         IntegerToString((long)r.tick_volume),IntegerToString(r.spread),
                         IntegerToString((long)r.real_volume),"0","0");
   if(written==0){Print("ARTIN V2 BLOCKED: CSV write failure ",GetLastError());return false;}
   FileFlush(g_file);
   // Only a successfully written complete row becomes the restart checkpoint.
   g_last_bar=r.time;
   return true;
  }

void Halt(const string reason)
  {
   Print("ARTIN V2 STOPPED WITHOUT TRADING: ",reason);
   g_halted=true;
   EventKillTimer();
  }

void RecoverClosedHistory()
  {
   if(g_halted||g_file==INVALID_HANDLE)return;
   if(!SafeAccountChart()){Halt("DEMO/symbol/timeframe changed");return;}
   if(!SeriesInfoInteger(_Symbol,PERIOD_M15,SERIES_SYNCHRONIZED))
     { Print("ARTIN V2: waiting for synchronized broker history");return; }

   int count=0;
   int start_pos=1;
   if(g_last_bar==0)
     {
      // First run: bootstrap most recent N CLOSED bars, never bar 0.
      int available=Bars(_Symbol,PERIOD_M15)-1;
      if(available<1)return;
      int wanted=MathMin(available,InpInitialClosedBars);
      count=MathMin(wanted,InpBatchBars);
      start_pos=1+(wanted-count); // oldest batch first, then recover the remainder
     }
   else
     {
      // iBarShift(exact=true) refuses silent skipping if broker history has
      // lost the last committed bar. No nearest-bar substitution is allowed.
      int anchor_shift=iBarShift(_Symbol,PERIOD_M15,g_last_bar,true);
      if(anchor_shift<1){Halt("last committed bar absent from exact broker history");return;}
      int pending=anchor_shift-1;
      if(pending<1)return;
      if(pending>InpMaxCatchupBars)
        {Halt("too many unreviewed missed bars; require full historical reconciliation");return;}
      count=MathMin(pending,InpBatchBars);
      start_pos=anchor_shift-count; // oldest pending batch FIRST, not latest N
     }
   if(count<=0 || start_pos<1)return;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int copied=CopyRates(_Symbol,PERIOD_M15,start_pos,count,rates);
   if(copied!=count)
     {Print("ARTIN V2: waiting for complete source batch, requested=",count,", got=",copied);return;}
   for(int i=0;i<copied;i++)
     if(!AppendClosedBar(rates[i]))
       {Halt("closed bar validation or file write failed");return;}
   Print("ARTIN V2: appended ",copied," closed bars, last=",
         TimeToString(g_last_bar,TIME_DATE|TIME_SECONDS));
  }

int OnInit()
  {
   if(!SafeAccountChart())return INIT_FAILED;
   if(InpPollSeconds<1||InpPollSeconds>60||InpInitialClosedBars<1||InpInitialClosedBars>5000
      ||InpBatchBars<1||InpBatchBars>1000||InpMaxCatchupBars<InpBatchBars
      ||InpMaxCatchupBars>500000)return INIT_PARAMETERS_INCORRECT;
   g_filename="artin_v13_demo_"+SafeFilenameToken(AccountInfoString(ACCOUNT_SERVER))+"_"
                +IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))+"_"
                +SafeFilenameToken(_Symbol)+"_M15_recovery_v2.csv";
   ResetLastError();
   // Keep one exclusive writer open while permitting readers.
   // Additional probes must not append concurrently.
   g_file=FileOpen(g_filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI
                   |FILE_COMMON|FILE_SHARE_READ,',');
   if(g_file==INVALID_HANDLE)
     {Print("ARTIN V2 BLOCKED: CSV open failed or another writer active ",GetLastError());return INIT_FAILED;}
   if(!ReadLastCommittedBar())
     {FileClose(g_file);g_file=INVALID_HANDLE;return INIT_FAILED;}
   if(!EventSetTimer(InpPollSeconds))
     {Print("ARTIN V2 BLOCKED: timer setup failed");FileClose(g_file);g_file=INVALID_HANDLE;return INIT_FAILED;}
   Print("ARTIN V2 DEMO CLOSED-BAR CAPTURE ONLY: ",g_filename,
         ". No orders, no signals, no network operations.");
   return INIT_SUCCEEDED;
  }

void OnTimer(){RecoverClosedHistory();}
void OnTick(){} // deliberately NO trading logic
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_file!=INVALID_HANDLE){FileFlush(g_file);FileClose(g_file);g_file=INVALID_HANDLE;}
  }
