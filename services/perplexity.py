import os
from dotenv import load_dotenv

from openai import OpenAI

load_dotenv()
plexKey = os.getenv("PLEX_KEY")


messages = [
    {
        "role": "system",
        "content": (
            "You are an artificial intelligence assistant and you need to "
            "engage in a helpful, detailed, polite conversation with a user."
        ),
    },
    {
        "role": "user",
        "content": ("How many stars are in the universe?"),
    },
]

client = OpenAI(api_key=plexKey, base_url="https://api.perplexity.ai")

# chat completion without streaming
response = client.chat.completions.create(
    model="sonar-pro",
    messages=messages,
)

content = response.choices[0].message.content
print(content)
citations = response.citations
print(citations)
