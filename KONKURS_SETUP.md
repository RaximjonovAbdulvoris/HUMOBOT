# Konkursni ishga tushirish

Konkurs anketasi: shahar, ism-familiya, telefon, bajarilgan buyurtmalar soni,
buyurtma sanasi. Guruh administratori tasdiqlamaguncha Sheetsga yuborilmaydi.

1. Konkurs guruhi `-5302408605` ga botni administrator qilib qo‘shing.
   Serverdagi `.env.production` fayliga `KONKURS_GROUP=-5302408605` qo‘shing yoki
   `bot_routes.json` ichida shu kalitga ID yozing. ID bo‘lmasa tugma anketani
   qabul qilmaydi.
2. Konkurs uchun berilgan Google Sheets faylining `Лист1` sahifasi ishlatiladi.
   Bo‘sh sahifaga birinchi tasdiqlangan ariza kelganda quyidagi sarlavhalar
   avtomatik qo‘yiladi:
   `Ariza kodi | Shahar | Ism familiya | Telefon | Buyurtmalar soni | Sana`.
   Toshkent, Namangan va boshqa shaharlarning barcha arizalari shu listga
   yoziladi; `Shahar` ustuni ularni ajratib turadi. Agar listda boshqa
   ustunlar yoki ma’lumotlar bo‘lsa, eksport rad qilinadi.
3. Mavjud Google Apps Script loyihasidagi `integrations/brand_sheets.gs` kodini
   yangilang. Script properties ichiga `KONKURS_SPREADSHEET_ID` qiymatini
   konkurs jadvalining IDsi qilib qo‘shing. Mavjud
   `HUMO_SECRET`, brend va Spectre IDlarini saqlang. Web app uchun **yangi
   versiya** deploy qiling; webhook URL o‘zgarsa server sozlamasini ham yangilang.
4. Test anketasini yuborib, guruhdagi rad javobi Sheetsga yozilmasligini,
   tasdiqlangan anketaning bir marta yozilishini tekshiring. Shundan so‘ng
   `humobot` xizmatini yangilangan kod bilan qayta ishga tushiring.

Konkurs guruhi IDsi va jadval havolasi aniqlanmaguncha production bot kodini
almashtirmang: mavjud Apps Script versiyasi konkurs yozuvini qabul qilmaydi.
