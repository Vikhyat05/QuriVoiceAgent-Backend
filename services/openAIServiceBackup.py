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


load_dotenv()
key = os.getenv("OPENAI_API_KEY")
print("Open AI", key)
# openai = OpenAI(api_key=key)
# client = AsyncOpenAI(api_key=key)
import json  # Ensure JSON is imported


class OpenAiService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=key)
        self.interrupt_event = asyncio.Event()
        self.interrupted = False

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

        # Remove prosody scores and other metadata
        messages: list[ChatCompletionMessageParam] = [
            {"role": m["role"], "content": m["content"]} for m in raw_messages
        ]

        print(messages[-1])
        memory.update_chat_history(custom_session_id, messages[-1])

        user_history = memory.get_chat_history(custom_session_id)

        print(user_history)

        # Create streaming chat completions
        chat_completion_chunk_stream = await self.client.chat.completions.create(
            messages=user_history,
            model="gpt-4o-mini",
            stream=True,
        )

        async for chunk in chat_completion_chunk_stream:
            # If interruption has been triggered, stop immediately
            if self.interrupt_event.is_set():
                print("Streaming interrupted by user request.")
                self.interrupted = True
                break

            # print("Token generation -----")
            # Convert the chunk to a dictionary
            if hasattr(chunk, "to_dict"):
                chunk_data = chunk.to_dict()
            else:
                chunk_data = chunk.__dict__  # Fallback to __dict__

            # Override system_fingerprint with custom_session_id
            if "system_fingerprint" in chunk_data and custom_session_id:
                chunk_data["system_fingerprint"] = custom_session_id

            if chunk_data["choices"][0]["finish_reason"] == "stop":
                print("Response Completed")
            # Serialize the chunk_data dictionary to JSON
            yield "data: " + json.dumps(chunk_data) + "\n\n"

        # If we exited without interruption, signal end of stream
        if not self.interrupted:
            yield "data: [DONE]\n\n"

    def trigger_interruption(self):
        """Trigger an interruption to stop ongoing response generation."""
        print("Triggered The interruption")
        self.interrupt_event.set()
        self.interrupted = True


# class OpenAiService:

#     def __init__(self):
#         self.client = AsyncOpenAI(api_key=key)

#     async def get_response(
#         self,
#         raw_messages: list[dict],
#         custom_session_id: Optional[str],
#     ) -> AsyncIterable[str]:
#         """Generates responses from OpenAI and streams modified chunks."""
#         # Remove prosody scores and other Hume metadata
#         messages: list[ChatCompletionMessageParam] = [
#             {"role": m["role"], "content": m["content"]} for m in raw_messages
#         ]

#         # Create streaming chat completions
#         chat_completion_chunk_stream = await self.client.chat.completions.create(
#             messages=messages,
#             model="gpt-4o-mini",
#             stream=True,
#         )

#         async for chunk in chat_completion_chunk_stream:
#             # Convert the chunk to a dictionary
#             chunk_data = chunk.model_dump(exclude_none=True)

#             # Override system_fingerprint with custom_session_id
#             if "system_fingerprint" in chunk_data and custom_session_id:
#                 chunk_data["system_fingerprint"] = custom_session_id

#             # Yield the modified chunk as a JSON string
#             yield "data: " + chunk_data.model_dump_json() + "\n\n"

#         # End of stream
#         yield "data: [DONE]\n\n"


# class OpenAiService:

#     def __init__(self, *, system_prompt: str, memory: Memory):

#         self.system_prompt = system_prompt

#         self.functions = [
#             {
#                 "name": "triggerWaitlist",
#                 "description": "This functions trigger the waitlist input box on the screen as soon as user agrees or ask to signup for waitlist",
#                 "parameters": {
#                     "type": "object",
#                     "properties": {
#                         "trigger_flag": {
#                             "type": "string",
#                             "description": "The trigger_flag parameter accepts two values: 'trigger' and 'close'. When set to 'trigger', it opens the waitlist input box, allowing user input. When set to 'close', it hides the waitlist input box, disabling further input",
#                         }
#                     },
#                     "required": ["trigger_flag"],
#                 },
#             }
#         ]

#         self.current_function = {"name": "", "arguments": ""}
#         # self.messages = [{"role": "system", "content": self.system_prompt}]
#         self.sessions = {}  # In-memory storage for chat histories
#         self.memory = memory
#         self.interrupt_event = asyncio.Event()
#         self.interrupted = False

#     def add_prosody_to_utterance(self, utterance: str, prosody: dict) -> str:
#         """
#         Enhances an utterance by appending prosody information derived from prosody analysis.

#         Args:
#             utterance (str): The original text utterance to be enhanced.
#             prosody (dict): A dictionary containing prosody features and their values.

#         Returns:
#             str: The enhanced utterance with prosody information appended.
#         """
#         if prosody:
#             prosody_string = ", ".join(prosody.keys())
#             return f"Speech: {utterance} {prosody_string}"
#         else:
#             return f"Speech: {utterance}"

#     async def get_responses(self, chat_history):

#         self.current_function = {"name": "", "arguments": ""}
#         try:
#             response = openai.chat.completions.create(
#                 model="gpt-4o-mini",
#                 messages=chat_history,
#                 max_tokens=1024,
#                 temperature=1,
#                 stream=True,
#                 function_call="auto",
#                 functions=self.functions,
#             )

#         except Exception as e:
#             print("Inside Error___________", e)
#             yield json.dumps({"type": "error", "message": str(e)}) + "\n"
#             return

#         for chunk in response:

#             # if self.interrupt_event.is_set():
#             #     print(
#             #         "Interruption detected inside Get_Response. Stopping response generation."
#             #     )
#             #     # self.interrupted = True
#             #     self.interrupt_event.clear()
#             #     break

#             delta = chunk.choices[0].delta
#             # print(f"---- Delta paramerters------{delta}")
#             is_function_call = False
#             finish_reason = chunk.choices[0].finish_reason

#             if delta.function_call:
#                 is_function_call = True

#                 if delta.function_call.name:
#                     # print("First If")
#                     self.current_function["name"] = delta.function_call.name
#                     print(self.current_function)
#                 if delta.function_call.arguments:
#                     # print("Second If")
#                     self.current_function["arguments"] += delta.function_call.arguments
#                     print(self.current_function)

#             # Handle regular content hasattr(delta, "content")
#             elif delta.content:
#                 # print("Regular content in process_stream", delta.content)
#                 # yield json.dumps({"type": "assistant_input", "text": chunk}) + "\n"
#                 yield json.dumps(
#                     {"type": "assistant_input", "text": delta.content}
#                 ) + "\n"

#             # Check if the function call is complete
#             if finish_reason == "function_call":
#                 print("Function call complete:", self.current_function)
#                 yield json.dumps(
#                     {"type": "function_call", "function": self.current_function}
#                 ) + "\n"
#                 break  # Exit the loop after function call is complete

#             # Check if the response is complete
#             if finish_reason == "stop":
#                 yield json.dumps({"type": "assistant_end"})
#                 break

#     # async def chat_stream(self, session_id: str):
#     #     c = 0

#     #     while True:
#     #         user_history = self.memory.get_chat_history(session_id)
#     #         print("Message History____________", user_history)
#     #         # print("Chat_Stream: New Message Recieved")
#     #         c += 1
#     #         # print(c)
#     #         has_function_call = False
#     #         current_function = None
#     #         assistant_response = ""
#     #         self.interrupted = False
#     #         self.interrupt_event.clear()  # Reset the event for future use
#     #         for chunk in self.get_responses(user_history):
#     #             print("Data Inside Chat stream _______________", chunk)
#     #             # Check for interruption

#     #             if self.interrupt_event.is_set():
#     #                 print(
#     #                     "Interruption detected in chat_stream. Stopping response generation."
#     #                 )
#     #                 print(
#     #                     "Updating memory with the partial response due to interruption."
#     #                 )

#     #                 if assistant_response.strip():  # Ensure there's something to save
#     #                     self.memory.update_chat_history(
#     #                         session_id,
#     #                         {"role": "assistant", "content": assistant_response},
#     #                     )
#     #                 # self.interrupted = True  # Mark as interrupted
#     #                 # self.interrupt_event.clear()  # Reset the event for future use
#     #                 break

#     #             data = json.loads(chunk)
#     #             # print("Data Inside Chat stream _______________", data)

#     #             if data["type"] == "error":
#     #                 yield data

#     #             if data["type"] == "function_call":

#     #                 has_function_call = True
#     #                 current_function = data["function"]

#     #                 self.memory.update_chat_history(
#     #                     session_id,
#     #                     {
#     #                         "role": "assistant",
#     #                         "content": None,
#     #                         "function_call": current_function,
#     #                     },
#     #                 )

#     #                 continue

#     #             if data.get("text") or data["type"] == "assistant_end":
#     #                 try:
#     #                     assistant_response += data.get("text", "")
#     #                     yield data  # Yield content chunks to the client
#     #                 except:
#     #                     yield data  # Yield content chunks to the client

#     #             if data["type"] == "assistant_end":
#     #                 self.memory.update_chat_history(
#     #                     session_id, {"role": "assistant", "content": assistant_response}
#     #                 )

#     #         # if self.interrupted:
#     #         #     print("Updating memory with the partial response due to interruption.")
#     #         #     if assistant_response.strip():  # Ensure there's something to save
#     #         #         self.memory.update_chat_history(
#     #         #             session_id, {"role": "assistant", "content": assistant_response}
#     #         #         )
#     #         #     self.interrupted = False
#     #         #     break

#     #         if has_function_call and current_function:
#     #             # Handle the function call
#     #             f_args = json.loads(current_function["arguments"])
#     #             print(f_args)
#     #             function_response = await self.handle_function_call(
#     #                 current_function["name"], f_args, session_id
#     #             )

#     #             if function_response:
#     #                 print(f"-----Function Response {function_response}")
#     #                 self.memory.update_chat_history(session_id, function_response)

#     #                 continue

#     #         break  # No more function calls, end the stream

#     async def chat_stream(self, session_id: str):
#         while True:
#             user_history = self.memory.get_chat_history(session_id)
#             has_function_call = False
#             current_function = None
#             assistant_response = ""
#             self.interrupted = False
#             self.interrupt_event.clear()
#             buffer = []

#             async for chunk in self.get_responses(user_history):
#                 if self.interrupt_event.is_set():
#                     if assistant_response.strip():
#                         self.memory.update_chat_history(
#                             session_id,
#                             {"role": "assistant", "content": assistant_response},
#                         )
#                     break

#                 data = json.loads(chunk)
#                 data["custom_session_id"] = session_id

#                 if data["type"] == "error":
#                     yield [data]
#                     continue

#                 if data["type"] == "function_call":
#                     has_function_call = True
#                     current_function = data["function"]
#                     self.memory.update_chat_history(
#                         session_id,
#                         {
#                             "role": "assistant",
#                             "content": None,
#                             "function_call": current_function,
#                         },
#                     )
#                     yield [data]
#                     break

#                 if data.get("text") or data["type"] == "assistant_end":
#                     assistant_response += data.get("text", "")
#                     buffer.append(data)

#                     if len(buffer) >= 10 or data["type"] == "assistant_end":
#                         yield buffer.copy()
#                         buffer.clear()

#                 if data["type"] == "assistant_end":
#                     self.memory.update_chat_history(
#                         session_id, {"role": "assistant", "content": assistant_response}
#                     )

#             if has_function_call and current_function:
#                 f_args = json.loads(current_function["arguments"])
#                 function_response = await self.handle_function_call(
#                     current_function["name"], f_args, session_id
#                 )
#                 if function_response:
#                     self.memory.update_chat_history(session_id, function_response)
#                     continue

#             break

#     def number_to_words(self, number):
#         """
#         Converts a number in string format into its word representation.

#         Args:
#             number (str): The number to convert, in string format.

#         Returns:
#             str: The word representation of the given number.
#         """
#         p = inflect.engine()
#         words = p.number_to_words(number)
#         return words

#     async def triggerWaitlist(self, trigger_flag: str, session_id: str) -> str:
#         waitlist_handler = await self.per_session_storage.getWaitListHandler(session_id)

#         if not waitlist_handler:
#             print(f"No waitlist handler found for session_id: {self.session_id}")
#             return "Waitlist handler not found"

#         instructions = {"trigger_flag": trigger_flag}
#         message = json.dumps(instructions)
#         await waitlist_handler.send_message(message)

#         print("----Executing uichange----")
#         return f"Wait List box is on the screen now"

#     async def handle_function_call(
#         self, f_name: str, f_args: Dict[str, Any], session_id: str
#     ):
#         if f_name == "triggerWaitlist":
#             result = await self.triggerWaitlist(f_args.get("trigger_flag"), session_id)
#             return {
#                 "role": "function",
#                 "name": f_name,
#                 "content": json.dumps({"Waitlist_Triggeres": result}),
#             }

#     def trigger_interruption(self):
#         """
#         Trigger an interruption to stop ongoing response generation.
#         """

#         print("Triggered The interuption")
#         self.interrupt_event.set()
#         self.interrupted = True
