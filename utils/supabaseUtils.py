import os
from supabase import create_client, Client
from postgrest import APIError

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

supabaseSync: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
supabaseAnonSync: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def fetchEpisodeContent(access_token, episode_id):
    supabaseAnonSync.postgrest.session.headers.update(
        {"Authorization": f"Bearer {access_token}"}
    )
    supabase_response = (
        supabaseAnonSync.table("episodes").select("*").eq("id", episode_id).execute()
    )

    return supabase_response.data


def fetchEpisodes(access_token):

    supabaseAnonSync.postgrest.session.headers.update(
        {"Authorization": f"Bearer {access_token}"}
    )

    supabase_response = supabaseAnonSync.table("episodes").select("*").execute()
    # supabase_response = (
    #     supabase.table("NotesFunctionCall").select("*").eq("userID", user_id).execute()
    # )

    return supabase_response.data


class SupaBaseFunc:

    def getUserId(accessToken):
        token = accessToken
        try:
            supabase_response = supabase.auth.get_user(token)
            userId = supabase_response.user.id
            return {"status": "verified", "UserID": userId}

        except Exception as e:
            error_message = str(e)
            if "token is expired" in error_message:
                return {
                    "status": "error",
                    "error": "token_expired",
                    "message": "Token has expired. Please refresh.",
                }

            else:
                return {
                    "status": "error",
                    "error": "authentication_failed",
                    "message": error_message,
                }

    def fetchNotes(access_token):
        supabase.postgrest.session.headers.update(
            {"Authorization": f"Bearer {access_token}"}
        )
        user_response = supabase.auth.get_user(access_token)
        print(user_response)

        try:
            notesData = (
                supabase.table("NotesFunctionCall")
                .select("*")  # ✅ No need to filter by userID explicitly
                .execute()
            )
            return notesData
        except APIError as e:
            print(f"Supabase API Error: {e}")
        return None
