# قاعده → کد → شاهد آزمون

منابع، جلسه:ثانیه‌اند. شرح کامل و تفاوت تفسیر فعلی با اصل آموزش در method_reference.json و مرجع فارسیِ تحویل آمده است. منبع کد، موتور قبلی نیست.

| قاعده | تابع/شناسه | منبع | آزمون اصلی |
|---|---|---|---|
|پولبک عادی|Engine._entry / PULLBACK_STANDARD|۱۶:۶۱۵..۱۱۰۹|هر۱۲شاخه در test_entry_examples|
|کلاسیک/Three/Star|REVERSAL_CLASSIC/THREE/STAR|۲۰:۲۱۸۹..۴۴۸۴|هر۱۲شاخه؛ زمینه PRZ در test_entry_review|
|لبهٔ دور همان OB/FVG|BREAK_STRONG|۲۱:۲۱۰۵..۲۲۶۱|test_zone_far_edge_immutable_trace_and_isolated_imports|
|شکست قوی/ضعیف/استثنای fullbody|BREAK_STRONG/WEAK_PIVOT/WEAK_FULLBODY_EXCEPTION|۲۱:۲۲۷۴..۳۱۵۳|test_weak_fullbody_exception_does_not_require_pivot_cross|
|خیلی‌قوی و نیمهٔ بدنه|BREAK_VERY_STRONG_RETEST|۲۱:۳۱۶۳..۳۴۷۴|test_very_strong_half_body_touch_without_closed_candle|
|سه فرم StopPunch|STOPPUNCH_*|۲۱:۳۹۴۷..۴۲۲۳؛۲۳:۴۶۹۴..۴۷۲۸|آزمون‌های samecolour/doji/tied/opposite در test_entry_review|
|شمار درست/غلط، نه پول|STOPPUNCH_DOJI_AHEAD/TIED|۲۱:۳۹۸۵..۴۰۶۹|test_doji_ahead_count_not_money_and_unextracted_day|
|استثنای PRZ در روند قوی|Engine._family_admission|۱۵:۳۴۴۳..۳۵۱۲|test_strong_trend_prz_exception_with_source_trace|
|نبود نگاه به آینده|_Reader.value / Fact.known_at|۲۱:۲۴۶..۳۰۹؛۲۳:۱۳۸۸..۱۴۳۵|test_future_required_fact_is_review|
|ریسک/حجم و حداقل لات|size_position|۲۵:۱۰۱۵..۱۲۸۲؛۲۶:۲۵۱۱..۲۹۱۷|۹آزمون capital|
|حرکت SL، نه بستن جزئی|move_stop / TradeMachine.manage|۲۵:۱۵۱۹..۲۹۱۹|test_reduce_riskfree_save_both_sides_no_realization|
|باکس ثابت|BoxPlan / TradeMachine._fixed|۲۶:۱۳۱۳..۲۲۹۱|آزمون fingerprint و تغییر قواعد|
|واقعیت fill/هزینه|account_fill / TradeMachine.close|۲۵:۲۱۴۹..۲۱۵۲؛شرح حسابداری|آزمون unknown، gap و CLOSED_PENDING_COST|

توابع قیمت/هزینه محاسبات یک مدل صریح‌اند؛ آستانهٔ تازه برای دوجی/قوت/گره یا الگوریتم اقتصادی تازه به نام مدرس اضافه نشده است. REVIEW ناشی از استخراج ناکامل ما با «مدرس ورود را ممنوع کرده» یکی نیست.
