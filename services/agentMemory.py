from utils.promptModifier import prompt


class Memory:
    def __init__(self):
        self.sessions = {}  # In-memory storage for chat histories

    def initialize_session(self, session_id: str):
        systemPrompt = prompt.getSystemPrompt(session_id)
        print(f"Got the System Prompt-----------\n{systemPrompt}")
        self.sessions[session_id] = [{"role": "system", "content": systemPrompt}]

    def get_chat_history(self, session_id: str):
        return self.sessions.get(session_id, [])

    def update_chat_historyv2(self, session_id: str, message: list):
        # self.initialize_session(session_id)
        self.sessions[session_id].extend(message)

    def update_chat_historyv3(self, session_id: str, message: dict):
        if session_id in self.sessions:
            self.sessions[session_id].append(message)

    def update_chat_history(self, session_id: str, message: dict):
        if session_id in self.sessions:
            self.sessions[session_id].append(message)
        else:
            self.initialize_session(session_id)
            self.sessions[session_id].append(message)

    def clear_session(self, session_id: str):
        # Remove the chat history from memory once the session is complete
        if session_id in self.sessions:
            del self.sessions[session_id]


memory = Memory()
