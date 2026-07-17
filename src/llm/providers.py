from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai

providers = {
    "OPENAI": lambda key: AsyncOpenAI(api_key=key),
    "ANTHROPIC": lambda key: AsyncAnthropic(api_key=key),
    "GEMINI": lambda key: genai.Client(api_key=key),
}
