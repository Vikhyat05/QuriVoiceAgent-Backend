class SessionManager:
    def __init__(self):
        self.sessions = {}  # {session_id: OpenAiService()}
        self.socket = {}
        self.user = {}

    def get_openai_service(self, session_id):
        return self.sessions.get(session_id)

    def set_openai_service(self, session_id, service):
        self.sessions[session_id] = service

    def set_socket_collection(self, session_id, client_socket):
        self.socket[session_id] = client_socket

    def get_socket(self, session_id):
        return self.socket.get(session_id)

    def set_user(self, session_id, userID):
        self.user[session_id] = userID

    def get_user(self, session_id):
        return self.user.get(session_id)


session_manager = SessionManager()
