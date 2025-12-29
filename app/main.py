# app/main.py
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.routes import users_router, chats_router, contact_router
from app.api.routes.websocket import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Anonymous Messenger API...")
    print("📡 WebSocket available at: ws://localhost:8000/ws/{user_id}?device_id={device_id}")
    yield
    # Shutdown
    print("👋 Shutting down...")

app = FastAPI(
    title="Anonymous Messenger API",
    description="Secure anonymous messaging platform",
    version="1.0.0",
    lifespan=lifespan
)

origins = [
    "http://localhost:3000",  # React/Vue dev сервер
    "http://127.0.0.1:3000",
    "http://0.0.0.0:8000",
    "http://localhost:8000",
]
# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роуты
app.include_router(
    users_router,
    prefix="/api/v1/users",
    tags=["users"]
)

app.include_router(
    chats_router,
    prefix="/api/v1/chats",
    tags=["chats"]
)

# WebSocket роут
app.include_router(
    websocket_router,
    prefix="/ws",
    tags=["websocket"]
)
app.include_router(
    contact_router,
    prefix="/api/v1/contacts",
    tags=["contacts"]
)

@app.get("/")
async def root():
    return {
        "message": "Anonymous Messenger API", 
        "status": "running",
        "websocket": "ws://localhost:8000/ws/{user_id}?device_id={device_id}"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/ws-info")
async def websocket_info():
    """Информация о WebSocket соединениях"""
    from app.websocket.manager import manager
    return {
        "online_users": len(manager.active_connections),
        "offline_messages": sum(len(q) for q in manager.offline_messages.values())
    }

@app.get("/ws-info/stats")
async def get_websocket_stats():
    """Получить полную статистику WebSocket соединений"""
    from app.websocket.manager import manager
    
    # Собираем статистику
    offline_queue_sizes = {
        str(user_id): len(messages) 
        for user_id, messages in manager.offline_messages.items()
    }
    
    return {
        "online_users": len(manager.active_connections),
        "total_offline_messages": sum(len(q) for q in manager.offline_messages.values()),
        "users_with_offline_messages": len(manager.offline_messages),
        "offline_queue_details": offline_queue_sizes,
        "server_time": datetime.now().isoformat(),
        "server_uptime": "not_implemented"  # Можно добавить логику отслеживания времени работы
    }