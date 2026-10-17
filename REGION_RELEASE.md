# Hudud guruhlarini ajratish

Hozirgi `@testthumo_bot` bir xil test guruhlaridan foydalanadi. Eski
arizalar buzilmasligi uchun bu holat yangi IDlar kiritilmaguncha saqlanadi.
Bot Telegram guruhlarini o‘zi yarata olmaydi: avval guruhlar ochilib, bot
administrator va xabar o‘chirish huquqiga ega bo‘lishi kerak.

`.env.test` fayliga quyidagi **14 ta alohida** guruh IDsi kiritiladi:
har hudud uchun 6 ta ariza guruhi va 1 ta arxiv. IDlar bir-birini
takrorlamasin. Ikkala haydovchi guruhi ham har hududda majburiy.

| Namangan | Toshkent |
| --- | --- |
| `DRIVER_GROUP_1` | `TASHKENT_DRIVER_GROUP_1` |
| `DRIVER_GROUP_2` | `TASHKENT_DRIVER_GROUP_2` |
| `BRAND_GROUP` | `TASHKENT_BRAND_GROUP` |
| `NAMANGAN_SPECTRE_GROUP` | `TASHKENT_SPECTRE_GROUP` |
| `NAMANGAN_INCOMPLETE_GROUP` | `TASHKENT_INCOMPLETE_GROUP` |
| `NAMANGAN_OTHER_PARK_GROUP` | `TASHKENT_OTHER_PARK_GROUP` |
| `ARCHIVE_GROUP` | `TASHKENT_ARCHIVE_GROUP` |

IDlar tayyor bo‘lgach `.env.test`ga `SEPARATE_REGION_GROUPS=1` qo‘shing.
`venv/bin/python scripts/run_test_bot.py --check` Telegram huquqlarini
tekshiradi. Tekshiruv o‘tmasa xizmatni restart qilmang. O‘tsa
`systemctl restart humobot-test` bilan yangi yo‘nalishlar ishga tushadi.

Asosiy bot uchun alohida token, saqlash papkasi, muhit sozlamalari va
systemd servisi kerak. `scripts/check_release_routes.py`ni asosiy botning
muhiti bilan bajaring; test bot tokeni rad etiladi. U bir xil yoki mavjud
bo‘lmagan guruh IDlarini va Sheets ulanish sozlamasini aniqlaydi.
Google Sheets amalda yozishini operator tasdiqlagan ikkita sinov Brend
arizasidan so‘ng `Ташкент` va `Наманган` varaqlarida tasdiqlang.
Spectre arizalari mavjud loyihaga ko‘ra bitta `Лист1` varag‘iga yoziladi.

Token va Google maxfiy kalitini chatga yoki gitga yubormang.
