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

