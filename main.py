from fastapi import FastAPI, WebSocketDisconnect, WebSocket, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from services.HumeConnectionService import ClientSocketManager
from services.agentService import initializeLLMSocket
import asyncio
from typing import AsyncIterable, Optional
import fastapi
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse
import openai
import os
from fastapi import HTTPException, Security
from services.OpenAiService import OpenAiService
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from utils.SessionManager import session_manager
from pydantic import BaseModel
import requests
from utils.supabaseUtils import supabase, SupaBaseFunc, fetchEpisodes
import uuid
from utils.promptModifier import prompt
from services.agentMemory import memory

app = FastAPI()
clientSocketManager = ClientSocketManager()
# agent = OpenAiService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
    allow_credentials=True,
)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


client_id = os.getenv("GOOGLE_CLIENT_ID")
client_secret = os.getenv("GOOGLE_CLIENT_SECRET")


# Redirect URL after successful login
WEB_REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5500/callback.html")
IOS_REDIRECT_URI = "myapp://oauthredirect"
# Define Gmail Scopes
GMAIL_SCOPES = "https://www.googleapis.com/auth/gmail.labels https://www.googleapis.com/auth/gmail.readonly"


@app.post("/chat/completions", response_class=StreamingResponse)
async def chat_completions_endpoint(request: fastapi.Request):
    """SSE endpoint to handle chat completions with Bearer token authentication."""
    request_json = await request.json()
    messages = request_json["messages"]
    # print("Received Messages:", messages)

    # Extract custom_session_id from query params
    custom_session_id = request.query_params.get("custom_session_id")
    print("Custom Session ID:", custom_session_id)
    agent = session_manager.get_openai_service(custom_session_id)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # Though X-Accel-Buffering is primarily for Nginx, it can be useful for some clients.
        "X-Accel-Buffering": "no",
    }

    # Return the streaming response
    return StreamingResponse(
        agent.get_response(messages, custom_session_id=custom_session_id),
        media_type="text/event-stream",
        headers=headers,
    )


@app.websocket("/llm")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await initializeLLMSocket(websocket)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, sessionId: str = Query(...)):
    auth_header = websocket.headers.get("Authorization")
    if not auth_header:
        await websocket.close()
        print("No Acess token")
        return

    # Parse the "Bearer <token>"
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer":
        await websocket.close()
        return

    response = SupaBaseFunc.getUserId(token)

    if response.get("status") == "verified":
        userID = response.get("UserID")
        print(userID)

        await websocket.accept()
        await clientSocketManager.intializeSocket(websocket, sessionId, userID)

    elif response.get("satus") == "error":
        await websocket.close()
        return


@app.get("/home")
def testing():
    return {"Messgage": "Working"}


#### Login and Signup endpoints ####


@app.get("/auth/login")
def google_login(request: Request):
    """
    Redirect user to Google Sign-In using Supabase OAuth with Gmail scopes.
    """

    user_agent = request.headers.get("User-Agent", "").lower()

    redirect_uri = "myapp://oauthredirect"

    try:
        response = supabase.auth.sign_in_with_oauth(
            {
                "provider": "google",
                "options": {
                    "redirect_to": redirect_uri,
                    "scopes": GMAIL_SCOPES,  # ✅ Correctly defined Gmail scopes
                    "query_params": {
                        "access_type": "offline",
                        "prompt": "consent",
                    },
                },
            }
        )
        print("This is Response", response)
        print(response.url)  # Debugging: Check if URL is correct
        return RedirectResponse(response.url)  # ✅ Fix applied: Use `.url`
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google Auth failed: {str(e)}")


@app.get("/auth/callback")
async def google_callback(request: Request):
    """
    Handles OAuth callback and exchanges the authorization code for a session.
    """
    # global provider_tokens
    code = request.query_params.get("code")  # Get 'code' from query parameters
    print(f"Received Code: {code}")

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code is missing")

    try:
        # Exchange the authorization code for a session
        auth_response = supabase.auth.exchange_code_for_session({"auth_code": code})

        print("Auth Response:", auth_response)

        if auth_response is None:
            raise HTTPException(status_code=400, detail="Supabase response is None")

        # Extract user object safely
        user = getattr(auth_response, "user", None)
        session = getattr(auth_response, "session", None)

        if not user:
            raise HTTPException(
                status_code=400, detail="Failed to retrieve user from session"
            )

        # Extract user metadata safely
        user_metadata = getattr(user, "user_metadata", {})

        user_data = {
            "id": user.id,
            "email": user.email,
            "name": user_metadata.get("full_name", "Unknown User"),
            "avatar_url": user_metadata.get("avatar_url", ""),
            "google_access_token": session.provider_token,
            "google_refresh_token": session.provider_refresh_token,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
        }

        return JSONResponse(
            content={"message": "User authenticated", "user": user_data},
            status_code=200,
        )

    except Exception as e:
        print(f"Error during authentication: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error during authentication: {str(e)}"
        )


@app.get("/get_episodes")
async def get_notes(Authorization: str = Header(...)):
    """
    Fetch all notes for the user based on access token.
    """

    # Extract the Bearer token
    print(Authorization)
    if not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=400, detail="Invalid token format")

    access_token = Authorization.split(" ")[1]
    supabase_response = fetchEpisodes(access_token=access_token)

    if not supabase_response:
        return JSONResponse(
            content=None,
            status_code=400,
        )

    return JSONResponse(
        content=supabase_response,
        status_code=200,
    )


@app.get("/auth/emails")
def fetch_latest_emails():
    """
    1) Exchange the code for a session to get the user's Google access token.
    2) Make a request to the Gmail API to fetch top 5 email subject lines.
    """
    global provider_tokens
    try:

        print(provider_tokens)
        access_token = provider_tokens["google_access_token"]
        messages_res = requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"maxResults": 5},  # top 5
            timeout=10,
        )
        messages_res.raise_for_status()

        messages_data = messages_res.json()
        messages = messages_data.get("messages", [])

        subject_lines = []
        for msg in messages:
            msg_id = msg["id"]
            # Get individual message metadata to retrieve Subject
            detail_res = requests.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "metadata", "metadataHeaders": ["Subject"]},
                timeout=10,
            )
            detail_res.raise_for_status()
            detail_data = detail_res.json()

            headers = detail_data.get("payload", {}).get("headers", [])
            # Extract the Subject header
            subject_line = next(
                (h["value"] for h in headers if h["name"] == "Subject"), "No Subject"
            )
            subject_lines.append(subject_line)

        return {"emails": subject_lines}

    except requests.RequestException as re:
        raise HTTPException(status_code=400, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching emails: {str(e)}")


@app.post("/auth/refresh")
def refresh_google_access_token(request: RefreshTokenRequest) -> dict:
    """Exchanges Google refresh token for a new access token."""

    # Replace with your actual Google Client ID and Secret
    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": request.refresh_token,
        "grant_type": "refresh_token",
    }

    response = requests.post(url, data=data)
    token_info = response.json()
    print("This is google_token_response", response)

    return JSONResponse(
        content=token_info,
        status_code=200,
    )


@app.get("/get_notes")
async def get_notes(Authorization: str = Header(...)):
    """
    Fetch all notes for the user based on access token.
    """
    # Extract the Bearer token
    print(Authorization)
    if not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=400, detail="Invalid token format")

    access_token = Authorization.split(" ")[1]
    print("This is Access Token", access_token)

    # Fetch notes from Supabase where userID matches
    supabase_response = SupaBaseFunc.fetchNotes(access_token)

    print("This is supabase response", supabase_response.data)
    if not supabase_response.data:
        return JSONResponse(
            content=None,
            status_code=400,
        )

    return JSONResponse(
        content=supabase_response.data,
        status_code=200,
    )


@app.get("/episodes/{episode_id}")
async def get_episode(
    episode_id: str,
    Authorization: str = Header(None),
    session_id: str = Query(
        ..., description="Session ID for tracking the session"
    ),  # Add this line
):
    if not Authorization:
        raise HTTPException(status_code=401, detail="No Authorization header found.")

    # Authorization should be in the form: "Bearer <token>"
    parts = Authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid bearer token format.")

    token = parts[1]

    # Log the data to console (or your preferred logger)

    print(f"Access Token: {token}")
    print(f"Episode ID: {episode_id}")
    print(f"Episode ID: {session_id}")

    # Delete the existing history for the session
    memory.clear_session(session_id)
    # Update the the system prompt for the session
    prompt.fetchEpisodeContent(token, episode_id, session_id)
    # Return a simple JSON response with 200 status
    return {
        "status": "OK",
        "message": f"Received episode {episode_id} with token: {token}",
    }
