"""
One shared function to build the Groq LLM client, so every node uses
the same model/temperature instead of instantiating it separately
and risking inconsistent settings.

temperature=0 because classification/extraction should be as
deterministic as possible -- we want the same message to reliably
produce the same intent/entities, not creative variation.
"""
import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Add it to a .env file in the project root."
            )
        _llm = ChatGroq(
            model="openai/gpt-oss-20b",
            temperature=0,
            api_key=api_key,
        )
    return _llm