// Independent, one-shot DEMO candle capture. No order/trade API is present.
#property strict
#property script_show_inputs
#property version "1.01"
#property description "Read-only ePlanet DEMO closed XAU M15 capture"

input string InpSymbol = "XAUUSD.st";
input int InpClosedBars = 512;

bool Guard(string &reason)
{
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
     { reason="TERMINAL_NOT_CONNECTED"; return false; }
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     { reason="DEMO_ACCOUNT_REQUIRED"; return false; }
   if(AccountInfoString(ACCOUNT_SERVER)!="ePlanet-MT5")
     { reason="EPLANET_SERVER_REQUIRED"; return false; }
   string company=AccountInfoString(ACCOUNT_COMPANY);
   StringToLower(company);
   if(StringFind(company,"eplanet")<0)
     { reason="EPLANET_COMPANY_REQUIRED"; return false; }
   if(InpSymbol!="XAUUSD.st" && InpSymbol!="XAUUSD")
     { reason="SYMBOL_NOT_ALLOWED"; return false; }
   if(InpClosedBars<1 || InpClosedBars>100000)
     { reason="COUNT_OUT_OF_BOUNDS"; return false; }
   return true;
}

bool ValidRate(const MqlRates &rate,const datetime current_open)
{
   if(rate.time<=0 || rate.time>=current_open || rate.time+900>current_open)
      return false;
   if(((long)current_open-(long)rate.time)%900!=0)
      return false;
   if(!MathIsValidNumber(rate.open) || !MathIsValidNumber(rate.high) ||
      !MathIsValidNumber(rate.low) || !MathIsValidNumber(rate.close))
      return false;
   if(rate.low<=0 || rate.high<rate.low ||
      rate.open<rate.low || rate.open>rate.high ||
      rate.close<rate.low || rate.close>rate.high)
      return false;
   if(rate.tick_volume<0 || rate.real_volume<0 || rate.spread<0)
      return false;
   return true;
}

string RateJSON(const MqlRates &rate)
{
   return "{\"time\":"+IntegerToString((long)rate.time)+
          ",\"open\":"+DoubleToString(rate.open,16)+
          ",\"high\":"+DoubleToString(rate.high,16)+
          ",\"low\":"+DoubleToString(rate.low,16)+
          ",\"close\":"+DoubleToString(rate.close,16)+
          ",\"tick_volume\":"+IntegerToString(rate.tick_volume)+
          ",\"spread\":"+IntegerToString(rate.spread)+
          ",\"real_volume\":"+IntegerToString(rate.real_volume)+"}";
}

void OnStart()
{
   const ulong all_start=GetMicrosecondCount();
   string reason="";
   if(!Guard(reason)) { Print("ARTIN_CAPTURE_BLOCKED: ",reason); return; }
   // Used only for an in-memory race check; never exported or printed.
   const long account_identity=AccountInfoInteger(ACCOUNT_LOGIN);
   const datetime fence=iTime(InpSymbol,PERIOD_M15,0);
   if(fence<=0) { Print("ARTIN_CAPTURE_BLOCKED: CURRENT_BAR_UNAVAILABLE"); return; }
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   const ulong receive_start=GetMicrosecondCount();
   ResetLastError();
   const int copied=CopyRates(InpSymbol,PERIOD_M15,1,InpClosedBars,rates);
   const ulong receive_us=GetMicrosecondCount()-receive_start;
   if(copied<=0)
     { Print("ARTIN_CAPTURE_BLOCKED: CLOSED_HISTORY_UNAVAILABLE code=",GetLastError()); return; }
   // Refuse a moving closure boundary; caller can rerun instead of publishing
   // a capture whose decision-time fence changed halfway through reception.
   if(iTime(InpSymbol,PERIOD_M15,0)!=fence)
     { Print("ARTIN_CAPTURE_BLOCKED: CURRENT_BAR_CHANGED_DURING_COPY"); return; }
   const ulong validate_start=GetMicrosecondCount();
   for(int i=0;i<copied;i++)
     {
      if(!ValidRate(rates[i],fence) || (i>0 && rates[i].time<=rates[i-1].time))
        { Print("ARTIN_CAPTURE_BLOCKED: INVALID_OR_DUPLICATE_CANDLE index=",i); return; }
     }
   const ulong validation_us=GetMicrosecondCount()-validate_start;
   // Account guard is rechecked immediately before publication; a chart/account
   // switch during the copy cannot pass on the original guard alone.
   if(!Guard(reason)) { Print("ARTIN_CAPTURE_BLOCKED: ",reason); return; }
   if(AccountInfoInteger(ACCOUNT_LOGIN)!=account_identity)
     { Print("ARTIN_CAPTURE_BLOCKED: ACCOUNT_CHANGED_DURING_COPY"); return; }
   const datetime captured_server_time=TimeCurrent();
   const ulong process_start=GetMicrosecondCount();
   string document="{\"schema\":\"artin_codex_capture_v1\",\"capture_magic\":\"ARTIN_CODEX_INDEPENDENT_READ_ONLY\","+
      "\"symbol\":\""+InpSymbol+"\",\"timeframe\":\"M15\",\"period_seconds\":900,"+
      "\"server\":\"ePlanet-MT5\",\"demo\":true,\"orders_enabled\":false,"+
      "\"native_server_time\":"+IntegerToString((long)captured_server_time)+","+
      "\"current_bar_open_native\":"+IntegerToString((long)fence)+","+
      "\"time_conversion_applied\":false,\"requested_closed_bars\":"+IntegerToString(InpClosedBars)+","+
      "\"received_closed_bars\":"+IntegerToString(copied)+","+
      "\"partial_history\":"+(copied<InpClosedBars ? "true" : "false")+","+
      "\"timing_us\":{\"receive\":"+IntegerToString((long)receive_us)+
      ",\"validation\":"+IntegerToString((long)validation_us)+"},\"bars\":[";
   for(int i=0;i<copied;i++)
     {
      if(i>0) document+=",";
      document+=RateJSON(rates[i]);
     }
   document+="]}\n";
   // FILE_TXT expands LF to CRLF. Use explicit UTF-8 bytes in binary mode so
   // exact write/readback checks compare the actual intended byte sequence.
   uchar payload[];
   const int encoded=StringToCharArray(document,payload,0,WHOLE_ARRAY,CP_UTF8);
   if(encoded<1 || ArrayResize(payload,encoded-1)!=encoded-1)
     { Print("ARTIN_CAPTURE_BLOCKED: UTF8_ENCODING_FAILED"); return; }
   const ulong process_us=GetMicrosecondCount()-process_start;
   const string directory="ArtinCodexIndependent";
   ResetLastError();
   if(!FolderCreate(directory,FILE_COMMON) && GetLastError()!=0)
     {
      // Existing directories are normal. FileOpen below is the decisive test.
      ResetLastError();
     }
   const string name=directory+"\\capture_"+IntegerToString((long)captured_server_time)+
      "_"+IntegerToString((long)GetTickCount64())+".json";
   const string temp=name+".tmp";
   const ulong store_start=GetMicrosecondCount();
   const int handle=FileOpen(temp,FILE_WRITE|FILE_BIN|FILE_COMMON);
   if(handle==INVALID_HANDLE)
     { Print("ARTIN_CAPTURE_BLOCKED: EXPORT_OPEN_FAILED code=",GetLastError()); return; }
   const uint written=FileWriteArray(handle,payload,0,ArraySize(payload));
   FileFlush(handle);
   FileClose(handle);
   if(written!=(uint)ArraySize(payload))
     { Print("ARTIN_CAPTURE_BLOCKED: EXPORT_WRITE_FAILED"); return; }
   // Unique names avoid overwriting any previous capture, including on retries.
   if(!FileMove(temp,FILE_COMMON,name,FILE_COMMON))
     { Print("ARTIN_CAPTURE_BLOCKED: EXPORT_PUBLISH_FAILED code=",GetLastError()); return; }
   const ulong store_us=GetMicrosecondCount()-store_start;
   const ulong verification_start=GetMicrosecondCount();
   const int verify_handle=FileOpen(name,FILE_READ|FILE_BIN|FILE_COMMON);
   if(verify_handle==INVALID_HANDLE)
     { Print("ARTIN_CAPTURE_BLOCKED: EXPORT_REOPEN_FAILED"); return; }
   const ulong size=FileSize(verify_handle);
   uchar read_back[];
   const uint read_count=FileReadArray(verify_handle,read_back,0,(int)size);
   FileClose(verify_handle);
   if(size!=(ulong)ArraySize(payload) || read_count!=(uint)size ||
      CharArrayToString(read_back,0,(int)size,CP_UTF8)!=document)
     { Print("ARTIN_CAPTURE_BLOCKED: EXPORT_READBACK_MISMATCH"); return; }
   const ulong verification_us=GetMicrosecondCount()-verification_start;
   Print("ARTIN_CAPTURE_OK file=",name," bars=",copied,
         " receive_us=",receive_us," validation_us=",validation_us,
         " processing_us=",process_us," storage_us=",store_us,
         " verification_us=",verification_us,
         " total_us=",GetMicrosecondCount()-all_start,
         " orders_submitted=0");
}
