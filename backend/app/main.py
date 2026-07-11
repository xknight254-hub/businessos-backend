from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import get_logger, new_correlation_id
from app.core.exceptions import register_exception_handlers
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.audit import audit_middleware
from app.core.ratelimit import RateLimitMiddleware
from app.core.handlers import register_handlers

logger = get_logger("businessos.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT == "production":
        import sentry_sdk
        sentry_sdk.init(dsn=getattr(settings, "SENTRY_DSN", ""))
    await init_db()
    register_handlers()
    logger.info("startup", extra={"environment": settings.ENVIRONMENT, "version": settings.VERSION})
    yield
    logger.info("shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    request.state.correlation_id = new_correlation_id()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.correlation_id
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=audit_middleware)
app.add_middleware(RateLimitMiddleware)


from app.modules.auth import router as auth_router
from app.modules.inventory.router import router as products_router
from app.modules.sales.router import router as sales_router
from app.modules.accounting.router import router as payments_router
from app.modules.crm.router import router as customers_router
from app.api.reports.routes import router as reports_router
from app.modules.ai import router as ai_router
from app.api.integrations.routes import router as integrations_router
from app.api.memory.routes import router as memory_router
from app.api.dna.routes import router as dna_router
from app.api.partner.routes import router as partner_router
from app.modules.automation import router as automation_router
from app.modules.notifications.router import router as notifications_router

app.include_router(auth_router)
app.include_router(products_router)
app.include_router(sales_router)
app.include_router(payments_router)
app.include_router(customers_router)
app.include_router(reports_router)
app.include_router(ai_router)
app.include_router(integrations_router)
app.include_router(memory_router)
app.include_router(dna_router)
app.include_router(partner_router)
app.include_router(automation_router)
app.include_router(notifications_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.VERSION}


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }
