# test_websocket_simple.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json

app = FastAPI()

# Разрешаем все CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Простой WebSocket без проверок
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    print(f"Пользователь {user_id} пытается подключиться...")
    
    await websocket.accept()
    print(f"✅ WebSocket подключен для пользователя: {user_id}")
    
    try:
        while True:
            # Получаем сообщение
            data = await websocket.receive_text()
            print(f"📩 Получено от {user_id}: {data}")
            
            try:
                message = json.loads(data)
                
                # Обрабатываем контакт-реквесты
                if message.get("type") == "contact_request":
                    recipient_id = message.get("recipientId")
                    print(f"📤 Пересылаю запрос на контакт к {recipient_id}")
                    
                    # В реальности нужно сохранять в БД и т.д.
                    await websocket.send_text(json.dumps({
                        "type": "contact_request",
                        "senderId": user_id,
                        "contactData": message.get("contactData")
                    }))
                    
                elif message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
            except json.JSONDecodeError:
                print(f"❌ Невалидный JSON от {user_id}")
                
    except Exception as e:
        print(f"❌ Ошибка WebSocket для {user_id}: {e}")

@app.get("/")
def root():
    return {"message": "WebSocket Test Server", "status": "running"}

if __name__ == "__main__":
    print("🚀 Запускаю тестовый WebSocket сервер на ws://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)