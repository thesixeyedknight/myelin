from typing import Dict, Any, Optional
from src.llm.providers import get_llm_provider, LLMProvider
from src.configs.settings import LLM_BACKEND, MODEL_NAME

class WriterAgent:
    def __init__(self, backend: str = LLM_BACKEND, model_name: str = MODEL_NAME):
        self.provider: LLMProvider = get_llm_provider(backend, model_name)

    def generate_report(self, text: str, mode: str = "summarize") -> str:
        if mode == "summarize":
            prompt = self._get_summary_prompt(text)
        elif mode == "comprehensive":
            prompt = self._get_comprehensive_prompt(text)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        return self.provider.generate(prompt, system_prompt="You are an expert scientific writer.")

    def _get_summary_prompt(self, text: str) -> str:
        return f"""
        Please provide a concise summary of the following scientific text.
        Focus on the main objectives, key methods, and primary findings.
        
        Text:
        {text[:10000]}  # Truncate to avoid context limit issues for now
        """

    def _get_comprehensive_prompt(self, text: str) -> str:
        return f"""
        Please generate a comprehensive structured report from the following scientific text.
        Use the following Markdown structure:
        
        # Title
        ## Abstract
        ## Introduction
        ## Methods
        ## Results
        ## Discussion
        ## Key References
        
        Text:
        {text[:15000]} # Truncate to avoid context limit issues for now
        """
