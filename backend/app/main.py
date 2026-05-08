from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import chat_routes
from .database import engine, Base

# Create database tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Travelo AI API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_routes.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
