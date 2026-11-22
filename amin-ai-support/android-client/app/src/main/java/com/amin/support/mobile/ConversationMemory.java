package com.amin.support.mobile;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Ephemeral, per-project, bounded multi-turn context. Never writes to disk. */
public final class ConversationMemory {
    private static final int MAX_PAIRS = 3;
    private static final int MAX_CHARS = 420;

    public static final class Turn {
        public final String role;
        public final String content;
        private Turn(String role, String content) {this.role=role;this.content=content;}
    }

    private final ArrayList<Turn> turns=new ArrayList<>();
    private String project="";

    public synchronized void clear() {turns.clear();project="";}

    public synchronized List<Turn> snapshot(String activeProject) {
        if(activeProject==null || !activeProject.equals(project))return Collections.emptyList();
        return Collections.unmodifiableList(new ArrayList<>(turns));
    }

    public synchronized void remember(String activeProject, String question, String answer) {
        if(activeProject==null || !activeProject.matches("[a-z][a-z0-9_-]{1,50}") ||
           question==null || answer==null || question.trim().isEmpty() || answer.trim().isEmpty()) return;
        if(!activeProject.equals(project)){turns.clear();project=activeProject;}
        turns.add(new Turn("user",shorten(question)));
        turns.add(new Turn("assistant",shorten(answer)));
        while(turns.size()>2*MAX_PAIRS) {turns.remove(0);turns.remove(0);}
    }
    private static String shorten(String text){
        String s=text.trim();
        return s.length()<=MAX_CHARS?s:s.substring(0,MAX_CHARS);
    }
}
