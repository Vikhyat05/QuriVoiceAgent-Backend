import json
import websockets


async def createHumeSocket(HUME_CONFIG, HUME_API_KEY):
    print("Inside hume socket creation")
    url = (
        f"wss://api.hume.ai/v0/evi/chat?config_id={HUME_CONFIG}&api_key={HUME_API_KEY}"
    )
    hume_socket = await websockets.connect(url, max_size=None)
    print("Connected to Hume WebSocket")
    return hume_socket


async def sendHumeSessionSettings(custom_session_id, hume_socket):
    """Send session settings to Hume after establishing a connection."""
    session_settings_message = {
        "type": "session_settings",
        "custom_session_id": custom_session_id,
        "audio": {"encoding": "linear16", "sample_rate": 44100, "channels": 1},
    }
    # Send session settings message through Hume WebSocket
    try:
        await hume_socket.send(json.dumps(session_settings_message))
    except Exception as e:
        print(e)
    print(f"Session settings sent with custom_session_id: {custom_session_id}")


async def sendMessageToHume(message, custom_session_id, hume_socket):
    # Ensure a connection to Hume exists
    try:
        # print(f"Raw message __________{message}")
        client_message = json.loads(message)
        # print(f"Formatted message __________{client_message}")
        if not hume_socket:
            print("Error: Hume connection not established.")
            return

        # Check if the message type is 'audio_input'
        if client_message.get("type") == "audio_input":

            # print("Audio Data ______________________", client_message)
            base64_data = client_message.get("data")
            # Create the message to send to Hume

            user_message = {
                "type": "audio_input",
                "data": base64_data,
                "custom_session_id": custom_session_id,
            }

            # print(f"Formatted message __________{user_message}")
            await hume_socket.send(json.dumps(user_message))

        elif client_message.get("type") == "user_input":
            print("got the text message")
            text_data = client_message.get("text")
            user_message = {
                "type": "user_input",
                "text": text_data,
                "custom_session_id": custom_session_id,
            }

            # Send the message to Hume
            await hume_socket.send(json.dumps(user_message))
        else:
            # Handle other message types if necessary
            print(f"Unsupported message type: {client_message.get('type')}")
    except Exception as e:
        print(f"Error: {e}")
