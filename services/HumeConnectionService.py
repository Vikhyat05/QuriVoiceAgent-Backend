from fastapi import WebSocketDisconnect
from utils.systemPrompt import SYSTEM_PROMPT
from services.agentMemory import memory
import websockets
import os
from dotenv import load_dotenv
import asyncio
from utils.HumeSocketUtils import (
    createHumeSocket,
    sendMessageToHume,
    sendHumeSessionSettings,
)
import json
from services.OpenAiService import OpenAiService
from utils.SessionManager import session_manager
from services.agentMemory import memory

load_dotenv()

HUME_CONFIG = os.getenv("HUME_CONFIG_ID")
print("This is the hume config id", HUME_CONFIG)
HUME_API_KEY = os.getenv("HUME_API_KEY")


class HumeConnection:
    def __init__(self, hume_socket, clientSocket, sessionId):
        self.hume_socket = hume_socket
        self.client_socket = clientSocket  # Will be set when a client is assigned
        self.session_id = sessionId

    def start_listener(self):
        self.hume_listener_task = asyncio.create_task(self.hume_listener())

    async def hume_listener(self):
        try:
            assistant_respone = ""
            while True:
                raw_message = await self.hume_socket.recv()

                # print("RAW MESSAGE RECEIVED_____________________", raw_message)
                message_dict = json.loads(raw_message)
                result = {
                    key: (value[:10] if key == "data" else value)
                    for key, value in message_dict.items()
                }
                if message_dict["type"] == "assistant_message":
                    print(message_dict)
                    assistant_respone += message_dict["message"]["content"]

                # print("RAW MESSAGE RECEIVED_____________________", result)
                if message_dict["type"] == "user_interruption":

                    memory.update_chat_history(
                        self.session_id,
                        {"role": "assistant", "content": assistant_respone},
                    )

                    # print(
                    #     "History from hume connection",
                    #     memory.get_chat_history(self.session_id),
                    # )
                    assistant_respone = ""

                    print("User interruption detected. Triggering stop.")
                    agent = session_manager.get_openai_service(
                        session_id=self.session_id
                    )
                    agent.trigger_interruption()
                    print("user_interruption")

                if message_dict["type"] == "audio_output":
                    print("Audio Input")

                if message_dict["type"] == "assistant_end":
                    print(assistant_respone)
                    memory.update_chat_history(
                        self.session_id,
                        {"role": "assistant", "content": assistant_respone},
                    )
                    print(
                        "History from hume connection",
                        memory.get_chat_history(self.session_id),
                    )
                    assistant_respone = ""

                # Send the message to the client
                # if message_dict["type"] == "audio_output":
                if self.client_socket:
                    print()
                    await self.client_socket.send_text(json.dumps(message_dict))
                else:
                    print(raw_message)
        except websockets.exceptions.ConnectionClosed:
            hume_connection_lost = {"type": "Error", "Status": "Hume Socket Is Closed"}
            await self.client_socket.send_text(hume_connection_lost)
            print("Hume WebSocket closed.")
        except asyncio.CancelledError:
            print("Hume listener task was canceled.")
        except Exception as e:
            hume_connection_Error = {"type": "Error", "Error": e}
            if self.client_socket:
                await self.client_socket.send_text(hume_connection_Error)
            print(f"Error in Hume listener: {e}")

    async def close(self):
        await self.hume_socket.close()
        self.hume_listener_task.cancel()


class ClientSocketManager:

    async def intializeSocket(self, websocket, sessionId, userID):
        clientWebsocket = websocket
        humeConnection = None
        session_manager.set_user(sessionId, userID)
        # agent = OpenAiService(system_prompt=SYSTEM_PROMPT, memory=memory)
        agent = OpenAiService()
        session_manager.set_openai_service(sessionId, agent)
        session_manager.set_socket_collection(sessionId, clientWebsocket)
        try:
            self.on_connection(clientWebsocket)
            # Generate a unique custom_session_id for this client
            custom_session_id = sessionId
            print(custom_session_id)
            # Create a new Hume connection for this client
            hume_socket = await createHumeSocket(HUME_CONFIG, HUME_API_KEY)

            print("Before hume connection")
            humeConnection = HumeConnection(hume_socket, clientWebsocket, sessionId)
            print("After hume connection")
            humeConnection.start_listener()
            await sendHumeSessionSettings(custom_session_id, hume_socket)

            while True:
                try:
                    message = await clientWebsocket.receive_text()
                    await sendMessageToHume(message, custom_session_id, hume_socket)
                except WebSocketDisconnect:
                    break
        except Exception as e:
            print(f"Error: {e}")
        finally:
            print("Client Connection Is Closed")
            # Close the Hume connection when the client disconnects
            if humeConnection is not None:
                await humeConnection.close()

    def on_connection(self, websocket):
        print(
            f"Connection Established with:{websocket.client.host}:{websocket.client.port}"
        )
