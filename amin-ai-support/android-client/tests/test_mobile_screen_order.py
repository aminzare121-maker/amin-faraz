"""Static UI regression: no moving answer below the advanced voice section."""
from pathlib import Path

src = Path(__file__).resolve().parents[1] / "app/src/main/java/com/amin/support/mobile/MainActivity.java"
s = src.read_text(encoding="utf8")
items = [
    'root.addView(question);',
    'send = button("پرسش از هوش پشتیبان");',
    'root.addView(answer);',
    'root.addView(section("مکالمهٔ صوتی فارسی"));',
    'root.addView(section("ارجاع به هوش مرکزی و پیگیری درخواست"));',
]
positions = [s.index(text) for text in items]
assert positions == sorted(positions), positions
assert "scroll.fullScroll(View.FOCUS_DOWN)" not in s
assert "scroll.smoothScrollTo(0," in s
assert 'voiceSettingsPanel.setVisibility(View.GONE)' in s
assert 'root.addView(voiceSettingsPanel)' in s
assert "https://your-support-server.example" not in s
print("PASS: chat/answer are before optional voice configuration, answer stays visible")
