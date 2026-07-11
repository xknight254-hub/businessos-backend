# BusinessOS

AI-powered operating system for Kenyan SMEs. Mobile-first, offline-capable,
M-Pesa native, eTIMS compliant. Reduces manual data entry by 90%.

## Quick Start

```bash
# Start development environment
cd docker && docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# Run tests
docker-compose exec api pytest

# API docs
open http://localhost:8000/docs
```

## Tech Stack

- **Mobile:** Flutter 3.x, Riverpod, drift/SQLCipher
- **Backend:** FastAPI, PostgreSQL 16, Redis 7, Celery
- **AI:** Ollama/llama.cpp, Prophet, pgvector, LangChain
- **Infrastructure:** Docker, K8s (EKS), Terraform, GitHub Actions

## Project Structure

```
businessos/
├── backend/          # FastAPI application
│   ├── app/          # Application code
│   ├── migrations/   # Alembic migrations
│   └── tests/        # Test suites
├── mobile/           # Flutter application
├── ai/               # AI/ML services
├── infrastructure/   # Terraform, K8s
├── docker/           # Docker configurations
└── docs/             # Documentation
```

## Documentation

| Document | Location |
|---|---|
| Architecture | `docs/Architecture.md` |
| API Reference | `http://localhost:8000/docs` |
| Implementation Plan | `/root/implementation/` |
| Design System | `/root/design/` |

## License

MIT
