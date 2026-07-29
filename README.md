# 🎫 Discord Advanced Ticket Bot System (نظام التذاكر المتقدم)

بوت ديسكورد احترافي وشامل لنظام التذاكر بلغة **Python** ومرتكز على **discord.py** و **Cogs** بدقة تفوق بوتات Ticket Tool و TicketsBot.

---

## 🌟 الميزات الرئيسية (Key Features)

- **لوحات تذاكر غير محدودة (Unlimited Panels)**: تخصيص الاسم، الوصف، الصور، الـ Banners، الألوان، والأقسام المتعددة.
- **إدارة التذاكر المتقدمة (In-Ticket Controls)**:
  - 📌 **Claim & Unclaim**: استلام وإلغاء استلام التذاكر.
  - 🔒 **Lock & Unlock**: قفل ومنع صاحب التذكرة من المراسلة.
  - ✏️ **Rename & Transfer**: تغيير اسم التذكرة ونقلها لقسم آخر.
  - 🔔 **Call Staff**: زر استدعاء وتنبيه فريق الدعم.
  - 📝 **Internal Notes**: إضافة ملاحظات خاصة للادارة فقط.
  - 👤 **Add / Remove Members**: إضافة وإزالة أعضاء للتذكرة.
  - 📌 **Priority & Department**: تحديد الأولوية (Low, Medium, High, Urgent).
- **نظام تقييم الدعم (5-Star Rating)**:
  - إرسال تقييم بالنجوم من 1 إلى 5 بعد إغلاق التذكرة مع تعليق اختياري.
  - حفظ التقييم في قاعدة البيانات وعرض إحصائيات كل إداري.
- **تصدير المحادثات الشامل (HTML Transcripts)**:
  - ملف HTML محمول بهيكل مشابه لديسكورد المظلم (Discord Dark Theme).
  - عرض صور، ملفات مرفقة، رسائل، وأوقات بدقة عالية.
- **الأمان والسيادة (Protection & Anti-Spam)**:
  - منع فتح أكثر من تذكرة واحدة في نفس القسم لكل مستخدم.
  - قائمة سوداء (Blacklist) وحظر المعتدين.
  - مهلة زامنية (Cooldown) لمنع السبام.
- **دعم اللغتين (Bilingual AR / EN)**:
  - دعم كامل للغة العربية والإنجليزية.

---

## 📁 هيكل المشروع (Project Structure)

```text
├── bot/
│   ├── config/
│   │   ├── settings.py         # إعدادات المتغيرات البيئية
│   │   └── locales.py          # قاموس النصوص العربية والإنجليزية
│   ├── database/
│   │   ├── db.py               # مدير قاعدة البيانات SQLite مع Indexes
│   │   ├── models.py           # الهياكل البيانية والبيانات
│   │   └── backup.py           # نظام النسخ الاحتياطي
│   ├── utils/
│   │   ├── embeds.py           # مصمم الـ Embeds التفاعلية
│   │   ├── permissions.py      # التحقق من صلاحيات الرتب
│   │   ├── antispam.py         # الحماية والـ Cooldowns
│   │   └── transcript_generator.py # مولد ملفات HTML Transcripts
│   ├── views/
│   │   ├── panel_view.py       # قائمة الاختيار Dropdown والـ Buttons للوحات
│   │   ├── ticket_controls.py  # أزرار الإدارة داخل التذكرة
│   │   ├── rating_view.py      # أزرار التقييم ومودال التعليق
│   │   └── modal_views.py      # المودالات والمدخلات
│   ├── cogs/
│   │   ├── tickets.py          # إنشاء وإنشاء القنوات
│   │   ├── management.py       # أوامر التحكم بالتذاكر
│   │   ├── stats.py            # أوامر الإحصائيات والأداء
│   │   ├── admin.py            # حظر المستخدمين والنسخ الاحتياطي
│   │   └── transcript.py       # أمر تصدير المحادثة
│   └── main.py                 # الملف الرئيسي لبدء البوت
├── requirements.txt            # المكتبات المطلوبة
├── .env.example                # نموذج الإعدادات البيئية
└── README.md                   # التوثيق
```

---

## 🚀 كيفية التشغيل (Quick Start)

### 1. تثبيت المكتبات
```bash
pip install -r requirements.txt
```

### 2. إعداد ملف `.env`
قم بإنشاء ملف `.env` ووضع توكن البوت:
```env
DISCORD_BOT_TOKEN="ضع_توكن_البوت_هنا"
DEFAULT_LANGUAGE="ar"
```

### 3. تشغيل البوت
```bash
python -m bot.main
```

---

## 📜 الأوامر المتاحة (Slash Commands)

- `/setup_panel`: نشر لوحة تذاكر تفاعلية في القناة.
- `/claim`: استلام التذكرة الحالية.
- `/unclaim`: إغلاق استلام التذكرة.
- `/close`: إغلاق التذكرة وإرسال التقييم.
- `/reopen`: إعادة فتح التذكرة.
- `/delete_ticket`: حذف قناة التذكرة نهائياً.
- `/priority`: تعيين أولوية التذكرة (Low, Medium, High, Urgent).
- `/note`: إضافة ملاحظة إدارية مخفية عن العميل.
- `/add_member`: إضافة عضو إلى التذكرة.
- `/remove_member`: إزالة عضو من التذكرة.
- `/transcript`: تحميل ملف المحادثة كـ HTML.
- `/ticket_stats`: عرض إحصائيات التذاكر وتقييمات الفريق.
- `/blacklist_add`: إضافة شخص إلى القائمة السوداء.
- `/blacklist_remove`: إزالة شخص من القائمة السوداء.
- `/backup_db`: إنشاء نسخة احتياطية من قاعدة البيانات.

---
حقوق النشر والملكية محفوظة. تم إعداده عبر Google AI Studio.
