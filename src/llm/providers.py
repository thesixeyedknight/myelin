from abc import ABC, abstractmethod
import os
from typing import List, Dict, Any, Optional
import ollama
import google.generativeai as genai

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        pass

class OllamaProvider(LLMProvider):
    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = ollama.chat(model=self.model_name, messages=messages)
        return response['message']['content']

class GeminiProvider(LLMProvider):
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.model_name = model_name
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel(model_name)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Gemini handles system prompts differently or via chat history, 
        # but for simple generation we can prepend it or use system_instruction if supported.
        # For simplicity in this abstraction:
        full_prompt = prompt
        if system_prompt:
             # Using system instruction at initialization is better but for per-call flexibility:
             full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"
        
        response = self.model.generate_content(full_prompt)
        return response.text

def get_llm_provider(backend: str, model_name: str) -> LLMProvider:
    if backend == "ollama":
        return OllamaProvider(model_name)
    elif backend == "gemini":
        return GeminiProvider(model_name)
    else:
        raise ValueError(f"Unknown LLM backend: {backend}")
