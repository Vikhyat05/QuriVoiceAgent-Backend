from fastapi import WebSocket, WebSocketDisconnect
from services.OpenAiService import OpenAiService
from utils.systemPrompt import SYSTEM_PROMPT
import json
from services.agentMemory import memory
import asyncio
from utils.SessionManager import session_manager

# agent = Agent(system_prompt=SYSTEM_PROMPT, per_session_storage=per_session_storage)


async def initializeLLMSocket(websocket: WebSocket):
    # agent = OpenAiService(system_prompt=SYSTEM_PROMPT, memory=memory)

    try:
        while True:
            data = await websocket.receive_text()
            hume_socket_message = json.loads(data)
            # print("this is hume websocket Message__________", hume_socket_message)

            session_id = hume_socket_message.get("custom_session_id")
            agent = session_manager.get_openai_service(session_id)

            # agent.trigger_interruption()

            print("This is the session ID ____________", session_id)

            # Parse the received message to extract the chat history.
            user_message = parse_hume_message(hume_socket_message)

            memory.update_chat_history(
                session_id, {"role": "user", "content": user_message}
            )

            # print(user_message)
            async for batch in agent.chat_stream(session_id):
                await asyncio.sleep(5)
                for response in batch:
                    print("Sending Response to Hume")
                    await websocket.send_text(json.dumps(response))

            # async for response in agent.chat_stream(session_id):
            #     response["custom_session_id"] = session_id
            #     # print("Message sent successfully")
            #     # print("Sending Response to Hume _____________________", response)
            #     # print("Sending Response to Hume")
            #     await asyncio.sleep(0.05)
            #     await websocket.send_text(json.dumps(response))
            # await asyncio.sleep(0.01)

    except WebSocketDisconnect as e:
        memory.clear_session(session_id)
        print(f"Client disconnected with code: {e.code}, reason: {e.reason}")


def parse_hume_message(messages_payload: dict) -> list[dict]:
    """
    Parses the payload of messages received from a client, constructing the chat history
    with contextualized utterances.

    Args:
        messages_payload (dict): The payload containing messages from the chat.

    Returns:
        list[dict]: The constructed chat history.
    """

    messages = messages_payload.get("messages", [])
    chat_history = [{"role": "system", "content": SYSTEM_PROMPT}]

    for idx, message in enumerate(messages):
        if not isinstance(message, dict):
            print(f"Message at index {idx} is not a dictionary. Skipping.")
            continue

        message_object = message.get("message", {})
        if not isinstance(message_object, dict):
            print(f"message['message'] at index {idx} is not a dictionary. Skipping.")
            continue

        # Safely get prosody_scores
        models = message.get("models", {})
        prosody = models.get("prosody")
        if prosody and isinstance(prosody, dict):
            prosody_scores = prosody.get("scores", {})
        else:
            prosody_scores = {}

        # Extract content from the message
        content = message_object.get("content", "")
        # Remove trailing period if present
        if content.endswith("."):
            content = content[:-1]

        # Append to chat history

        # print("this is the conetnt being fed to the model", content)
        role = message_object.get("role", "user")
        if role == "user":
            chat_history.append({"role": "user", "content": content})
        elif role == "assistant":
            chat_history.append({"role": "assistant", "content": content})

    return content


def add_prosody_to_utterance(utterance: str, prosody: dict) -> str:
    """
    Enhances an utterance by appending prosody information derived from prosody analysis.

    Args:
        utterance (str): The original text utterance to be enhanced.
        prosody (dict): A dictionary containing prosody features and their values.

    Returns:
        str: The enhanced utterance with prosody information appended.
    """
    if prosody:
        prosody_string = ", ".join(prosody.keys())
        return f"Speech: {utterance} {prosody_string}"
    else:
        return f"Speech: {utterance}"


def parse_hume_messagev2(messages_payload: dict) -> list[dict]:
    filtered_messages = [
        {"role": message["role"], "content": message["content"]}
        for message in messages_payload["messages"]
        if message["content"]  # Exclude messages where content is empty
    ]

    return filtered_messages
