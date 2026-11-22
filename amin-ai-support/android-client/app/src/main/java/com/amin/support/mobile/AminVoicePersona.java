package com.amin.support.mobile;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/**
 * The Amin Voice Persian-language narration layer (original app code).
 *
 * Deliberately lightweight: lexical corrections, spoken punctuation,
 * segment-level pauses, restrained pitch/rate. Speech *waveforms* still come
 * from the selected Android TTS voice. This is NOT an independently trained
 * neural voice, and makes no claim of reproducing ChatGPT's proprietary voice.
 */
public final class AminVoicePersona {
    public static final int CONVERSATIONAL = 0;
    public static final int DELIBERATE = 1;
    public static final int MAX_INPUT = 3200;
    public static final int MAX_CHUNK = 165;

    public static final String DEMO =
            "سلام! من هوش امین هستم. می‌تونیم فارسی و شمرده صحبت کنیم. "
            + "مثلاً در متاتریدر پنج، حد ضرر و حد سود را جداگانه بررسی می‌کنیم. "
            + "اگر اینترنت قطع بشه، پاسخ جدید ChatGPT دریافت نمی‌کنم.";

    public static final class Phrase {
        public final String text;
        public final int pauseMs;

        public Phrase(String text, int pauseMs) {
            this.text = text;
            this.pauseMs = pauseMs;
        }
    }

    private AminVoicePersona() {}

    public static float rate(int style) {
        return style == DELIBERATE ? 0.90f : 0.98f;
    }

    public static float pitch(int style) {
        return style == DELIBERATE ? 0.99f : 1.01f;
    }

    public static String normalize(String value) {
        if (value == null || value.trim().isEmpty()) return "";
        String t = value.length() > MAX_INPUT ? value.substring(0, MAX_INPUT) : value;
        // Never read a code block, token, pasted URL, or markup aloud.
        t = t.replaceAll("(?s)```.*?```", " بخشی از کد ");
        t = t.replaceAll("\\[([^\\]\\r\\n]{1,90})\\]\\(https?://[^)\\s]{1,500}\\)", "$1");
        t = t.replaceAll("(?i)https?://\\S+", " پیوند اینترنتی ");
        t = t.replaceAll("(?m)^\\s{0,3}#{1,6}\\s*", "");
        t = t.replaceAll("(?m)^\\s*[-*]\\s+", "");
        t = t.replace("**", "").replace("__", "").replace("`", "");
        t = t.replace('ي', 'ی').replace('ك', 'ک');
        t = t.replaceAll("[\\u0000-\\u0008\\u000B\\u000C\\u000E-\\u001F]", " ");
        // Spoken forms are explicit but conservative; text displayed on screen
        // is NEVER changed and this layer never changes model instructions.
        t = t.replaceAll("(?i)(?<![A-Za-z])XAUUSD(?![A-Za-z])", "اونس طلای جهانی");
        t = t.replaceAll("(?i)(?<![A-Za-z])MT5(?![A-Za-z])", "متاتریدر پنج");
        t = t.replaceAll("(?i)(?<![A-Za-z])SL(?![A-Za-z])", "حد ضرر");
        t = t.replaceAll("(?i)(?<![A-Za-z])TP(?![A-Za-z])", "حد سود");
        t = t.replaceAll("(?i)(?<![A-Za-z])GitHub(?![A-Za-z])", "گیت هاب");
        t = t.replaceAll("(?i)(?<![A-Za-z])ChatGPT(?![A-Za-z])", "چت جی پی تی");
        t = t.replaceAll("(?i)(?<![A-Za-z])API(?![A-Za-z])", "اِی پی آی");
        // Preserve useful sentence boundaries; collapse horizontal spacing.
        t = t.replaceAll("[ \\t\\x0B\\f]+", " ");
        t = t.replaceAll("\\n{3,}", "\\n\\n");
        return t.trim();
    }

    public static List<Phrase> plan(String raw, int style) {
        String t = normalize(raw);
        if (t.isEmpty()) return Collections.emptyList();
        ArrayList<Phrase> parts = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        for (int i = 0; i < t.length(); i++) {
            char ch = t.charAt(i);
            boolean newline = ch == '\n';
            if (newline) {
                flush(parts, current, 250, style);
                continue;
            }
            current.append(ch);
            // Natural phrase completion; commas should not break tiny phrases.
            boolean sentence = ch == '؟' || ch == '?' || ch == '!' || ch == '.'
                    || ch == '؛' || ch == ';';
            boolean comma = ch == '،' || ch == ',';
            if (sentence && current.length() > 8) {
                flush(parts, current, ch == '؟' || ch == '?' ? 260 : 220, style);
            } else if (comma && current.length() >= 65) {
                flush(parts, current, 130, style);
            } else if (current.length() >= MAX_CHUNK && (ch == ' ' || ch == '،'
                    || ch == ',' || ch == ':' || ch == '-')) {
                flush(parts, current, 105, style);
            } else if (current.length() >= MAX_CHUNK + 24) {
                flush(parts, current, 105, style);
            }
        }
        flush(parts, current, 0, style);
        if (!parts.isEmpty()) {
            // Never add an artificial silence after the last syllable.
            Phrase last = parts.get(parts.size() - 1);
            parts.set(parts.size() - 1, new Phrase(last.text, 0));
        }
        return Collections.unmodifiableList(parts);
    }

    private static void flush(List<Phrase> pieces, StringBuilder current,
                              int pause, int style) {
        String phrase = current.toString().trim();
        current.setLength(0);
        if (phrase.isEmpty()) return;
        int finalPause = pause;
        if (style == DELIBERATE) finalPause = Math.min(380, (pause * 6) / 5);
        pieces.add(new Phrase(phrase, finalPause));
    }
}
