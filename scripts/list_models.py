"""List available Gemini models."""
import sys
sys.path.insert(0, ".")

from google import genai
from src.configs.settings import SETTINGS

client = genai.Client(api_key=SETTINGS.gemini_api_key)

print("Available models:")
print("-" * 60)
for model in client.models.list():
    print(f"{model.name}")
    if hasattr(model, 'supported_generation_methods'):
        print(f"  Supported: {model.supported_generation_methods}")
