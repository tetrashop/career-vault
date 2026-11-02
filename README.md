# CareerVault — MVP

> ⚠️ **Status: Prototype / MVP** — Not production-ready for persistent data.

A minimal FastAPI service for a personal "career identity wallet": authenticated users can upload documents (education, financial, achievements, identity) and get a unified profile with SHA-256 integrity fingerprints.

## 🚀 Live Demo

**[https://career-vault-tan.vercel.app/docs](https://career-vault-tan.vercel.app/docs)**

> **Note on Data Persistence:** This demo runs on Vercel Serverless with SQLite stored in `/tmp`. **Data resets on every cold start.** For real use, migrate to PostgreSQL.

## Features

- JWT authentication (HS256) with `pbkdf2_sha256` password hashing
- Document upload with SHA-256 checksum
- Per-user profile with aggregated summary
- Audit log for every upload
- Swagger UI at `/docs`

## Stack

FastAPI · SQLAlchemy 2 · SQLite · Pydantic v2 · python-jose · passlib

## API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | – | Create account |
| POST | `/api/auth/login` | – | Get JWT token |
| POST | `/api/documents` | JWT | Upload a document |
| GET | `/api/documents` | JWT | List your documents |
| GET | `/api/profile` | JWT | Full profile + summary |
| GET | `/health` | – | Health check |

## Deployment (Vercel)

1. Fork this repo
2. Import to Vercel → Framework Preset: **FastAPI**
3. Set environment variable `SECRET_KEY` (generate with `python3 -c "import secrets;print(secrets.token_hex(32))"`)
4. Deploy

## Limitations

- **No persistent storage** — SQLite in `/tmp` resets on cold starts
- No file encryption at rest (only SHA-256 integrity)
- No real OCR or content verification
- No rate limiting, CSRF, or CORS hardening

## License

MIT — see [LICENSE](LICENSE).

## Sample Output

```json
{
  "user": { "full_name": "رامین اجلال", "email": "ramin.resume@example.com" },
  "summary": "4 verified: education=1, financial=1, achievement=1, identity=1",
  "documents": [
    { "doc_type": "education",   "title": "کارشناسی ارشد مهندسی نرم‌افزار", "issuer": "دانشگاه تهران" },
    { "doc_type": "financial",   "title": "گواهی تسویه حساب",           "issuer": "بانک ملت" },
    { "doc_type": "achievement", "title": "مقام اول هکاتون هوش مصنوعی", "issuer": "دانشگاه شریف" },
    { "doc_type": "identity",    "title": "کارت ملی هوشمند",            "issuer": "ثبت احوال" }
  ]
}
```

عنوان پروژه: CareerVault – نمونه اولیه (MVP) یک کیف پول هویت حرفه‌ای (Career Identity Wallet)
نویسنده/پژوهشگر: رامین اجلال
لینک دموی زنده: career-vault-tan.vercel.app

🌟 چشم‌انداز و ایده (The Vision)

ایده اولیه این پژوهش، خلق سیستمی بود که فراتر از یک رزومه سنتی عمل کند؛ سیستم‌ی که بتواند تمام سوابق هویتی، تحصیلی، مالی و دستاوردهای یک فرد را به‌صورت یکپارچه، امن و قابل اثبات جمع‌آوری کند. پرسش پژوهشی این بود: «چگونه می‌توان با استفاده از فناوری‌های وب مدرن، اصالت اسناد و هویت دیجیتال افراد را بدون نیاز به واسطه‌های پیچیده تضمین کرد؟»

🧠 ابعاد پژوهشی و نویسندگی (Research & Writing)

این پروژه صرفاً یک محصول نرم‌افزاری نیست، بلکه حاصل یک فرآیند مستندسازی و حل مسئله سیستماتیک است:

· تحقیق و توسعه (R&D) در محیط‌های محدود: بخش عمده‌ای از توسعه این پروژه در محیط شبیه‌سازی‌شده ترمینال (Termux روی اندروید) انجام شد. این چالش نیازمند پژوهش در مورد مدیریت وابستگی‌های پایتون، کامپایل کدهای Rust (برای pydantic-core) و مهندسی معکوس خطاهای مربوط به سیستم‌عامل اندروید بود که تماماً در مستندات پروژه ثبت شده است.
· مستندسازی فنی (Technical Writing): طراحی مستندات API با استاندارد OpenAPI (Swagger) و نگارش فایل README.md شفاف، به‌گونه‌ای که هر توسعه‌دهنده دیگری بتواند بدون دانش پیش‌زمینه، پروژه را اجرا و تست کند.
· تفکر انتقادی در معماری: درک محدودیت‌های زیرساخت‌های Serverless (مانند Vercel) و پذیرش آگاهانه محدودیت‌هایی مثل «نبود فایل‌سیستم پایدار» برای رسیدن به یک دموی زنده، نشان‌دهنده یک تصمیم‌گیری مهندسی آگاهانه و مستند است.

🏗️ معماری و دستاوردهای فنی (Architecture & Engineering)

پروژه بر پایه یک استک مدرن و با تمرکز بر امنیت و ماژولار بودن طراحی شده است:

· بک‌اند و طراحی API: استفاده از FastAPI و Pydantic v2 برای اعتبارسنجی دقیق داده‌ها، و SQLAlchemy برای تعامل با دیتابیس.
· امنیت و احراز هویت: پیاده‌سازی مکانیزم JWT (JSON Web Tokens) به همراه هش کردن رمز عبور با الگوریتم‌های امن. درگاه‌های حساس با OAuth2PasswordBearer محافظت می‌شوند.
· اثبات اصالت داده (Data Integrity): استفاده از تابع هش SHA-256 برای تولید «اثر انگشت دیجیتال» (Digital Fingerprint) برای هر سند آپلود شده. این ویژگی تضمین می‌کند که حتی یک بایت تغییر در سند، شناسایی می‌شود.
· تجمیع و هوش تجاری (Aggregation): طراحی الگوریتمی برای دسته‌بندی اسناد (تحصیلی، مالی، دستاورد، هویتی) و تولید یک خلاصه رزومه داینامیک به‌صورت Real-time.

🚀 استقرار و مهندسی عملیات (Deployment & DevOps)

انتقال پروژه از محیط محلی به محیط ابری شامل غلبه بر چالش‌های متعدد بود:

· استقرار (Deploy) موفق روی پلتفرم Vercel با وجود محدودیت‌های شدید محیط Serverless برای فایل‌سیستم.
· عیب‌یابی (Debugging) خطاهای مربوط به Routing (مسیریابی)، محیط‌های ایزوله و محافظت‌های شبکه‌ای پلتفرم.
· مدیریت متغیرهای محیطی (Environment Variables) برای حفظ امنیت کلیدهای رمزنگاری.

📈 نتایج قابل اندازه‌گیری (Business Impact / Results)

· امکان ثبت‌نام و احراز هویت کامل با پشتیبانی از کاراکترهای یونیکد (فارسی و انگلیسی).
· امکان آپلود و دسته‌بندی ۴ نوع سند مختلف.
· تولید خودکار خلاصه رزومه (مثال: 4 verified: education=1, financial=1, achievement=1, identity=1).
· ارائه یک رابط کاربری تعاملی (Swagger UI) برای تست آسان بدون نیاز به کدنویسی.
