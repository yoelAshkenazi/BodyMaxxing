# BodyMaxxing

Production-ready, highly optimized, and secure cross-platform health and fitness tracking application.

## Core Stack
- **Backend**: FastAPI, SQLModel, Alembic, asyncpg, Pydantic v2
- **Frontend**: Flet (Python-based Flutter framework with responsive layout and Pyodide web compilation)
- **AI Integration**: Pydantic AI with OpenAI/Anthropic models and structured outputs
- **Security**: OAuth2 Password Bearer, JWT, Argon2 password/refresh token hashing, SlowAPI rate limiting, BOLA protection
- **Testing**: pytest, pytest-asyncio, pytest-cov (>=80% coverage)

## Architecture
- **Trunk-Based Development**: Discrete feature branches, rebased frequently, merged to `main` upon passing test suites.
- **Asynchronous Execution**: Fully async database transactions via `asynccontextmanager` session injection.
- **OWASP API Security**: Implicit user-id scoping on all data operations to prevent Broken Object Level Authorization (BOLA).
