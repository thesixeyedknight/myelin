"""Quick test to verify usage tracking."""
import sys
sys.path.insert(0, ".")

from src.agent.llm import LLMClient

print("Testing usage tracking...")
client = LLMClient()

# Make a simple request
text, usage, tier = client.generate(
    "You are a helpful assistant.",
    "Say 'Test' in one word.",
    tier="lite"
)

print(f"Response: {text}")
print(f"Tier used: {tier}")
print(f"Tokens: {usage.get('total_token_count', 0)}")

print("\n✓ Request logged to work/api_usage_audit.csv")
print("Run: python scripts/usage_report.py to view stats")
