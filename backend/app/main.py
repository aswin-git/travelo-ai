from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from .routes import chat_routes
from .routes import user_routes
from .database import engine, Base

# Import all models so Base.metadata knows about them
from .models import place_model  # noqa: F401
from .models import user_model   # noqa: F401

# Create database tables if they don't exist
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: DB init error (likely concurrent creation): {e}")

app = FastAPI(title="Travelo AI API", version="1.0.0")

# Configure CORS — reads from ALLOWED_ORIGINS env var in production
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_routes.router)
app.include_router(user_routes.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

