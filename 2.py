# main.py (FastAPI Backend)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
import asyncio
import uvicorn
import json # Import json for message parsing

app = FastAPI()

# Configure CORS to allow requests from your frontend.
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:8001",
    "[http://127.0.0.1](http://127.0.0.1)",
    "[http://127.0.0.1:8000](http://127.0.0.1:8000)",
    "[http://127.0.0.1:8001](http://127.0.0.1:8001)",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSocket connections mapped by client ID
# { "client_id": WebSocket_object }
active_connections: Dict[str, WebSocket] = {}

@app.websocket("/ws/chat/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    Handles WebSocket connections for the chat system.
    Each client connects with a unique `client_id` provided in the URL path.
    The server stores this connection and handles incoming messages.
    """
    await websocket.accept()
    active_connections[client_id] = websocket
    print(f"Client '{client_id}' connected. Total active connections: {len(active_connections)}")

    # Send a system message to the newly connected client
    await websocket.send_text(json.dumps({"type": "system_message", "message": f"Welcome, your ID is: {client_id}"}))

    try:
        while True:
            # Listen for incoming messages from the client
            data = await websocket.receive_text()
            print(f"Received message from '{client_id}': {data}")

            try:
                message_data = json.loads(data)
                message_type = message_data.get("type")

                if message_type == "chat_message":
                    sender_id = message_data.get("sender_id")
                    recipient_id = message_data.get("recipient_id")
                    subject = message_data.get("subject", "") # Get new subject, default to empty string
                    body = message_data.get("body", "")       # Get new body, default to empty string

                    # --- DEBUG PRINTS START ---
                    print(f"DEBUG: sender_id='{sender_id}', type={type(sender_id)}")
                    print(f"DEBUG: recipient_id='{recipient_id}', type={type(recipient_id)}")
                    print(f"DEBUG: subject='{subject}', type={type(subject)}")
                    print(f"DEBUG: body='{body}', type={type(body)}")
                    print(f"DEBUG: Condition check: recipient_id={bool(recipient_id)}, (subject or body)={bool(subject or body)}")
                    # --- DEBUG PRINTS END ---

                    if recipient_id and (subject or body): # Ensure recipient and at least one content field
                        # Prepare the message to be sent to the recipient
                        payload = {
                            "type": "chat_message",
                            "sender_id": sender_id,
                            "subject": subject, # Include subject in payload
                            "body": body        # Include body in payload
                        }
                        # Find the recipient's WebSocket and send the message
                        recipient_websocket = active_connections.get(recipient_id)
                        if recipient_websocket:
                            try:
                                await recipient_websocket.send_text(json.dumps(payload))
                                print(f"Message from '{sender_id}' to '{recipient_id}' - Subject: '{subject}', Body: '{body}'")
                            except WebSocketDisconnect:
                                print(f"Recipient '{recipient_id}' disconnected during send attempt.")
                                # Clean up disconnected client immediately
                                if recipient_id in active_connections:
                                    del active_connections[recipient_id]
                            except Exception as e:
                                print(f"Error sending message to '{recipient_id}': {e}")
                        else:
                            print(f"Recipient '{recipient_id}' not found or not connected.")
                            # Optionally send a "recipient not found" message back to the sender
                            await websocket.send_text(json.dumps({"type": "system_message", "message": f"Recipient '{recipient_id}' is not online."}))
                    else:
                        print(f"Invalid chat message format from '{client_id}'. Missing recipient or message content.")
                        await websocket.send_text(json.dumps({"type": "system_message", "message": "Invalid message format. Missing recipient or message content."}))
                else:
                    print(f"Unknown message type '{message_type}' from '{client_id}'.")
                    await websocket.send_text(json.dumps({"type": "system_message", "message": "Unknown message type."}))

            except json.JSONDecodeError:
                print(f"Received non-JSON message from '{client_id}': {data}")
                await websocket.send_text(json.dumps({"type": "system_message", "message": "Please send messages in JSON format."}))

    except WebSocketDisconnect:
        # This exception is raised when a client disconnects.
        print(f"Client '{client_id}' disconnected.")
    except Exception as e:
        # Catch any other unexpected errors
        print(f"WebSocket error for client '{client_id}': {e}")
    finally:
        # Ensure the connection is removed from the dictionary when it closes.
        if client_id in active_connections:
            del active_connections[client_id]
        print(f"Active connections remaining: {len(active_connections)}")

# Simple root endpoint for testing purposes
@app.get("/")
async def read_root():
    return {"message": "Real-time Chat Server is running!"}

# To run this FastAPI application:
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
