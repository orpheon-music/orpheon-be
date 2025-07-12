import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Orpheon BE",
    description="Backend service for Orpheon",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"], summary="Root endpoint")
def read_root():
    return {"message": "Welcome to Orpheon BE!"}


@app.post("/api/v1/auth/register", tags=["Auth"], summary="User Registration")
def register_user():
    return {"message": "User registration endpoint"}


@app.post("/api/v1/auth/login", tags=["Auth"], summary="User Login")
def login_user():
    return {"message": "User login endpoint"}


@app.get("/api/v1/auth/session", tags=["Auth"], summary="Check User Session")
def check_session():
    return {"message": "User session check endpoint"}


def main():
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
