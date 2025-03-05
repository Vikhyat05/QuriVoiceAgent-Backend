from typing import AsyncIterable, Optional
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam
import json
import os
import inflect
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, Any
from services.agentMemory import memory
import asyncio
from openai import AsyncOpenAI
import os
import json
import os
from supabase import create_client, Client
from utils.SessionManager import session_manager
import uuid
from utils.promptModifier import prompt

file_lock = asyncio.Lock()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

load_dotenv()
plexKey = os.getenv("PLEX_KEY")
key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


notesModelHistory = [
    {
        "role": "system",
        "content": 'You are a note-taking assistant. Your task is to analyze the conversation history and extract structured notes in JSON format. The output should strictly follow this structure:\n\n{\n  "Topic": "String",\n  "Content": "Markdown formatted text"\n}\n\n### Instructions:\n- **Topic**: A concise title summarizing the key discussion point.\n- **Content**: Well-structured notes in Markdown format.\n  - Use headings (`#`), bullet points (`-`), and code blocks (` ``` `) where appropriate.\n  - Summarize key insights, steps, or explanations relevant to the conversation.\n\n### Constraints:\n- **Do not add any additional text outside of the JSON format.**\n- Ensure the output is valid JSON and follows the specified structure exactly.\n\nYour goal is to generate clean, structured, and useful notes while strictly adhering to the given format.',
    }
    # {
    #     "role": "system",
    #     "content": """You are a note-taking assistant. Analyze the conversation history and create structured markdown notes.
    #     The notes should in json format as shown below
    #     {"Topic": String,
    #     "Content": markdown
    #     }
    #     Note: Make sure you only give notes in the above json format no extra sentence of confirmation
    #     """,
    # }
]

functions = [
    {
        "name": "SaveNotes",
        "description": "Save information from the conversation to notes",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "SendNotes",
        "description": "Send the user's notes to them",
        "parameters": {
            "type": "object",
            "properties": {
                "flag": {
                    "type": "boolean",
                    "description": "True to send notes, False to cancel",
                }
            },
            "required": ["flag"],
        },
    },
    {
        "name": "openNotes",
        "description": "Opens the collection of notes for the user",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic or description about the specific notes given by the user (optional). Defaults to None if not provided.",
                }
            },
        },
    },
    {
        "name": "websearch",
        "description": "Fetches real-time information from the internet. Use this function when a user requests the latest updates, news, or any information that requires an online search.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query for retrieving relevant information from the internet.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetchContent",
        "description": "Retrieves episode content for either a specific main topic or the entire episode.",
        "parameters": {
            "type": "object",
            "properties": {
                "topicIndexOrAll": {
                    "type": "string",
                    "description": "Specify the index of the main topic (as a string) or 'all' to fetch the entire content.",
                }
            },
            "required": ["topicIndexOrAll"],
        },
    },
]


print("Open AI", key)


class OpenAiService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=key)
        self.interrupt_event = asyncio.Event()
        self.interrupted = False
        self.user_history = ""
        self.sessionId = ""

        # self.current_function = {"name": "", "arguments": ""}
        # self.function_arg = ""
        # self.assistant_response = ""

    def fetchContent(self, topic_index_or_all, sessionId):
        """
        Fetches the content from the episode structure.
        - If topic_index_or_all is an integer (e.g. 0, 1, 2, ...),
        it returns the subtopics and content for that specific main topic.
        - If topic_index_or_all is "all", it returns the subtopics and content for all main topics.
        """

        episode_data = prompt.getEpisodeContent(sessionId=sessionId)
        episode_data = json.loads(episode_data)
        # Convert episode_data keys (excluding 'EpisodeName') to a list for indexing
        main_topics_list = [k for k in episode_data.keys() if k != "EpisodeName"]

        if topic_index_or_all == "all":
            # Return the content for all main topics
            all_content = {}
            for topic_key in main_topics_list:
                all_content[topic_key] = episode_data[topic_key]
            return json.dumps(all_content)
        else:
            # Convert the input to integer
            idx = int(topic_index_or_all)
            # Return the content for the selected main topic
            topic_key = main_topics_list[idx]
            return json.dumps({topic_key: episode_data[topic_key]})

    def searchAgent(self, messages):
        searchAgent = OpenAI(api_key=plexKey, base_url="https://api.perplexity.ai")
        response = searchAgent.chat.completions.create(
            model="sonar-pro",
            messages=messages,
        )

        return response

    async def websearch(self, query, sessionID):
        client_socket = session_manager.get_socket(sessionID)

        searchAgentHistory = [
            {
                "role": "system",
                "content": "You are an AI assistant designed to provide helpful and keep your answers concise while ensuring clarity and usefulness in the conversation.",
            }
        ]
        searchAgentHistory.append(
            {
                "role": "user",
                "content": (query),
            }
        )
        results = self.searchAgent(searchAgentHistory)
        content = results.choices[0].message.content
        citations = results.citations
        print(citations)

        message_dict = {"type": "web", "links": citations}
        try:
            await client_socket.send_text(json.dumps(message_dict))
        except:
            print("Could not get the links")

        print(content)

        return content

    async def openNotes(self, sessionID, topic=None):
        client_socket = session_manager.get_socket(sessionID)

        if topic:
            print(topic)
        else:
            message_dict = {"type": "UI_Change", "instruction": "openNotes"}
            try:
                await client_socket.send_text(json.dumps(message_dict))
            except:
                return "Could not open the notes"

        return "Notes are on the screen now"

    async def assistantResponse(self, memory):
        # Async streaming response
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=memory,
            temperature=0,
            stream=True,
            functions=functions,
            function_call="auto",
        )

        async for chunk in response:
            yield chunk
            # asyncio.sleep(0.05)

    def SendNotes(self, flag):
        if flag:
            return "Here are your notes:\n" + open("notes.txt").read()
        return "Note sharing canceled"

    async def NoteTakingAssistant(self, memory):
        # Async note generation
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=memory,
            max_tokens=1024,
            temperature=0,
        )
        return response.choices[0].message.content

    async def SaveNotes(self, session_id):
        async def background_save(notesMem, session_id):
            try:
                content = await self.NoteTakingAssistant(notesMem)
                print("Generated Content: ", content)

                async with file_lock:
                    user_id_str = session_manager.get_user(session_id)
                    print("this is user_id", user_id_str)
                    try:
                        user_id = str(uuid.UUID(user_id_str))
                    except ValueError:
                        print(f"Invalid UUID format: {user_id_str}")
                        return "Unable to save the note due to some error"
                    data = {
                        "text": content,
                        "session_id": session_id,
                        "user_id": user_id,
                    }
                    response = (
                        supabase.table("NotesFunctionCall").insert(data).execute()
                    )
                    print("Supabase Response:", response)
                    print("(Notes successfully saved to Supabase)")

            except Exception as e:
                print(f"\nError saving notes to Supabase: {e}")

        notesMem = notesModelHistory + self.user_history[1:]
        print("Notes agent Memory_______", notesMem)
        asyncio.create_task(background_save(notesMem, session_id))
        return "I've started saving your notes in Supabase. We can continue talking while I save them."

    # async def SaveNotes(self):
    # async def background_save(notesMem):
    #     print("File exists:", os.path.exists("notes.txt"))
    #     print("File path:", os.path.abspath("notes.txt"))

    #     try:
    #         # Generate notes content asynchronously
    #         content = await self.NoteTakingAssistant(notesMem)
    #         print("Content: ", content)

    #         # Non-blocking file write using thread executor
    #         def write_to_file():
    #             print("Content Inside Write to File", content)
    #             with open("notes.txt", "a") as file:
    #                 file.write(f"{content}\n\n")
    #                 file.flush()

    #         async with file_lock:
    #             await asyncio.to_thread(write_to_file)
    #             print("\n(Notes successfully saved)")

    #     except Exception as e:
    #         print(f"\nError saving notes: {e}")

    # # Start background task without waiting
    # notesMem = notesModelHistory + self.user_history[1:]
    # print("Notes agent Memory_______", notesMem)
    # asyncio.create_task(background_save(notesMem))
    # return (
    #     "I've started saving your notes. We can continue talking while I save them."
    # )

    async def functionCallingHandler(self, callingData, sessionId):
        func_name = callingData["name"]
        if func_name == "SaveNotes":
            return {
                "role": "function",
                "name": func_name,
                "content": await self.SaveNotes(sessionId),
            }
        elif func_name == "SendNotes":
            func_response = self.SendNotes(callingData["arguments"]["flag"])
            return {"role": "function", "name": func_name, "content": func_response}

        elif func_name == "websearch":
            func_response = await self.websearch(
                callingData["arguments"]["query"], self.sessionId
            )
            return {"role": "function", "name": func_name, "content": func_response}

        elif func_name == "fetchContent":
            func_response = self.fetchContent(
                callingData["arguments"]["topicIndexOrAll"], self.sessionId
            )
            return {"role": "function", "name": func_name, "content": func_response}

        elif func_name == "openNotes":
            topic = callingData["arguments"].get(
                "topic"
            )  # Get topic or None if missing
            if topic is not None:
                return {
                    "role": "function",
                    "name": func_name,
                    "content": await self.openNotes(self.sessionId, topic),
                }

            else:
                return {
                    "role": "function",
                    "name": func_name,
                    "content": await self.openNotes(self.sessionId),
                }

        return None

    async def get_response(
        self,
        raw_messages: list[dict],
        custom_session_id: Optional[str],
    ) -> AsyncIterable[str]:
        """
        Generates responses from OpenAI and streams modified chunks.
        Checks for interruption in every iteration to stop immediately.
        """
        # Clear any previous interrupt flag
        self.interrupt_event.clear()
        self.interrupted = False

        self.sessionId = custom_session_id
        # Remove prosody scores and other metadata
        messages: list[ChatCompletionMessageParam] = [
            {"role": m["role"], "content": m["content"]} for m in raw_messages
        ]

        # print(messages[-1])
        memory.update_chat_history(custom_session_id, messages[-1])

        self.user_history = memory.get_chat_history(custom_session_id)

        # print(self.user_history)

        # Create streaming chat completions
        # chat_completion_chunk_stream = await self.client.chat.completions.create(
        #     messages=user_history,
        #     model="gpt-4o-mini",
        #     stream=True,
        # )
        response_finished = True
        function_calling = False

        while True:
            current_function = {"name": "", "arguments": ""}
            function_arg = ""

            async for chunk in self.assistantResponse(self.user_history):
                # If interruption has been triggered, stop immediately
                if self.interrupt_event.is_set():
                    print("Streaming interrupted by user request.")
                    self.interrupted = True
                    break

                # Convert the chunk to a dictionary
                if hasattr(chunk, "to_dict"):
                    chunk = chunk.to_dict()
                else:
                    chunk = chunk.__dict__  # Fallback to __dict__

                # print("Chunk Dict_____", chunk)
                # Override system_fingerprint with custom_session_id
                if "system_fingerprint" in chunk and custom_session_id:
                    chunk["system_fingerprint"] = custom_session_id

                delta = chunk["choices"][0]["delta"]
                finish_reason = chunk["choices"][0]["finish_reason"]
                # print("Delta_______", delta)

                # if delta.content:
                #     assistant_response += delta.content
                #     print(delta.content, end="", flush=True)

                if "function_call" in delta:
                    if "name" in delta["function_call"]:
                        current_function["name"] = delta["function_call"]["name"]
                    if "arguments" in delta["function_call"]:
                        function_arg += delta["function_call"]["arguments"]

                if finish_reason == "stop":
                    print("Response Completed")

                    response_finished = True
                    function_calling = False

                elif finish_reason == "function_call":
                    current_function["arguments"] = json.loads(function_arg)
                    self.user_history.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "function_call": {
                                "name": current_function["name"],
                                "arguments": function_arg,
                            },
                        }
                    )
                    response_finished = False
                    function_calling = True

                elif "content" in delta:
                    response_finished = False

                    print("Chunk_Data_____")
                    yield "data: " + json.dumps(chunk) + "\n\n"

            if function_calling:
                func_response = await self.functionCallingHandler(
                    current_function, custom_session_id
                )
                self.user_history.append(func_response)
                print(self.user_history)
                print(f"\n{func_response['content']}")
                response_finished = False
                function_calling = False

                continue

            if response_finished:
                if not self.interrupted:
                    yield "data: [DONE]\n\n"

                break

        # If we exited without interruption, signal end of stream
        if not self.interrupted:
            yield "data: [DONE]\n\n"
            asyncio.sleep(0.05)

    def trigger_interruption(self):
        """Trigger an interruption to stop ongoing response generation."""
        print("Triggered The interruption")
        self.interrupt_event.set()
        self.interrupted = True
