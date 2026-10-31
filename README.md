# CareerVault — MVP

> ⚠️ **Status: Prototype / MVP** — Not production-ready. See [Limitations](#limitations).

A minimal FastAPI service for a personal "career identity wallet":
authenticated users can upload documents (education, financial, achievements,
identity) and get a unified profile with SHA-256 integrity fingerprints.

## Features

- JWT authentication (HS256) with `pbkdf2_sha256` password hashing
- Document upload with SHA-256 checksum
- Per-user profile with aggregated summary
- Audit log for every upload
- Swagger UI at `/docs`

## Stack

FastAPI · SQLAlchemy 2 · SQLite · Pydantic v2 · python-jose · passlib

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -c "import secrets;print('SECRET_KEY='+secrets.token_hex(32))" >> .env
python3 app.py
```

Open http://127.0.0.1:8000/docs

API

Method Path Auth Description
POST /api/auth/register – Create account
POST /api/auth/login – Get JWT token
POST /api/documents JWT Upload a document
GET /api/documents JWT List your documents
GET /api/profile JWT Full profile + summary
GET /health – Health check

Limitations

This is a learning/portfolio project. It does not yet implement:

· File encryption at rest (only integrity via SHA-256)
· Real OCR or content verification (verified is set unconditionally)
· Entity resolution across issuers
· LLM-based resume generation
· Digital signatures or blockchain anchoring
· Rate limiting, HTTPS, CSRF, CORS hardening

Production checklist (before deploying)

☐ Set a strong SECRET_KEY via environment
☐ Switch SQLite → PostgreSQL
☐ Replace plain-text uploads with encrypted storage (S3 + KMS)
☐ Add bcrypt (currently pbkdf2_sha256 for Termux compatibility)
☐ Restrict CORS to specific origins
☐ Put behind Nginx + HTTPS
☐ Add rate limiting (slowapi)
☐ Add tests

License

MIT — see LICENSE.
