package com.amin.support.mobile;
public final class ConversationMemoryTest {
 public static void main(String[] args){
   ConversationMemory memory=new ConversationMemory();
   if(!memory.snapshot("support").isEmpty())throw new AssertionError();
   for(int i=0;i<7;i++)memory.remember("support","question "+i,"answer "+i);
   java.util.List<ConversationMemory.Turn> turns=memory.snapshot("support");
   if(turns.size()!=6 || !turns.get(0).content.equals("question 4") ||
      !turns.get(5).content.equals("answer 6"))throw new AssertionError("last 3 pairs only");
   if(!memory.snapshot("faraz").isEmpty())throw new AssertionError("cross-project leak");
   memory.remember("faraz","private","reply");
   if(!memory.snapshot("support").isEmpty())throw new AssertionError("project change not isolated");
   memory.clear();
   if(!memory.snapshot("faraz").isEmpty())throw new AssertionError("clear failed");
   memory.remember("support","x".repeat(1000),"y".repeat(1000));
   if(memory.snapshot("support").get(0).content.length()>420)throw new AssertionError("unbounded");
   System.out.println("PASS: temporary per-project three-turn memory");
 }
}
