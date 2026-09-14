from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from uvicorn import run
import database
import translate
from auth import get_current_user
from database import is_blocked, save_message, get_user_language, get_contacts
import os

app = FastAPI()
connections = {}


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    try:
        mobile = get_current_user("Bearer " + token)
    except:
        await websocket.close()
        return

    await websocket.accept()

    connections.setdefault(mobile, set()).add(websocket)

    try:
        while True:
            data = await websocket.receive_json()

            receiver = data["receiver"]
            message = data["message"]

            # Block check
            if is_blocked(receiver, mobile):
                continue

            # Save message
            save_message(receiver, message, mobile)

            # Send message if receiver is online
            if receiver in connections:
                preferred_lang = get_user_language(receiver)

                translated_message = await translate.translate_text(
                    message,
                    preferred_lang
                )

                receiver_contacts = get_contacts(receiver)
                is_known = any(
                    c["mobile"] == mobile
                    for c in receiver_contacts
                )

                for ws in connections[receiver]:
                    await ws.send_json({
                        "sender_mobile": mobile,
                        "message": translated_message,
                        "type": "new",
                        "is_unknown_sender": not is_known
                    })

    except WebSocketDisconnect:
        if mobile in connections:
            connections[mobile].discard(websocket)

            if not connections[mobile]:
                del connections[mobile]


app.include_router(database.router, prefix="/database", tags=["Postgres"])

app.include_router(translate.router, prefix="/translate", tags=["Translate"])

@app.get("/api_checker")
async def api_checker():
    return JSONResponse(content="API Test Successful")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    run(app, host="0.0.0.0", port=port)