package com.amin.support.mobile;

import java.util.List;

/** JVM-only functional tests: text and pacing, NOT sound-quality evidence. */
public final class AminVoicePersonaTest {
    private static void check(boolean ok, String why) {
        if (!ok) throw new AssertionError(why);
    }

    public static void main(String[] args) {
        String cleaned = AminVoicePersona.normalize(
                "سلام! لینک [راهنمای GitHub](https://example.org/secrets?key=abc) را ببین. "
                + "MT5 و XAUUSD را جدا بررسی کن. ```python\nprint('secret')\n```");
        check(cleaned.contains("گیت هاب"), "GitHub should be speakable in Persian");
        check(cleaned.contains("متاتریدر پنج"), "MT5 pronunciation");
        check(cleaned.contains("اونس طلای جهانی"), "XAUUSD pronunciation");
        check(!cleaned.contains("example.org"), "URL must not be spoken");
        check(!cleaned.contains("secret"), "source snippets and credentials must not be read");
        check(AminVoicePersona.normalize(null).isEmpty(), "Null is safe");
        check(AminVoicePersona.normalize(" ").isEmpty(), "Whitespace is safe");
        check(AminVoicePersona.normalize("كیفیت، ايران")
                .contains("کیفیت"), "Arabic yeh and kaf normalization");
        check(AminVoicePersona.pitch(AminVoicePersona.CONVERSATIONAL) > 0.9f,
                "Natural pitch in safe range");
        check(AminVoicePersona.rate(AminVoicePersona.DELIBERATE)
                < AminVoicePersona.rate(AminVoicePersona.CONVERSATIONAL),
                "Deliberate speech rate must be slower");

        List<AminVoicePersona.Phrase> speech = AminVoicePersona.plan(
                "سلام! حالت چطوره؟ امروز برنامه را بررسی کردم. "
                + "برای سفارش‌های جدید حد ضرر و حد سود را توضیح می‌دهم.",
                AminVoicePersona.CONVERSATIONAL);
        check(speech.size() >= 3, "Sentence pauses expected");
        check(speech.get(0).pauseMs >= 120, "First sentence must have a pause");
        check(speech.get(speech.size()-1).pauseMs == 0, "No artificial final silence");
        for (AminVoicePersona.Phrase phrase : speech) {
            check(!phrase.text.trim().isEmpty(), "No empty TTS utterances");
            check(phrase.text.length() <= AminVoicePersona.MAX_CHUNK + 24,
                    "No excessively long TTS chunk");
            check(phrase.pauseMs >= 0 && phrase.pauseMs <= 380,
                    "Speech pauses are bounded");
        }
        String longLine = "با برنامهٔ هوش امین گفت‌وگو می‌کنیم ".repeat(160);
        List<AminVoicePersona.Phrase> longPlan =
                AminVoicePersona.plan(longLine, AminVoicePersona.DELIBERATE);
        check(!longPlan.isEmpty() && longPlan.size() < 35,
                "Long text bounded by maximum input");
        check(AminVoicePersona.plan(null, AminVoicePersona.CONVERSATIONAL).isEmpty(),
                "No TTS on empty input");
        check(AminVoicePersona.DEMO.contains("هوش امین"), "Amin demo voice exists");
        System.out.println("PASS: Amin Voice Persian segmentation, pacing, terms, and privacy");
    }
}
