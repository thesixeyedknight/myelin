"""Test the cascading fallback system."""
import sys
sys.path.insert(0, ".")

import pytest
from src.agent.llm import LLMClient
from src.agent.rate_limits import MODEL_MANAGER
from src.configs.settings import SETTINGS

@pytest.mark.skipif(not SETTINGS.gemini_api_key, reason="API key required")
@pytest.mark.integration
def test_basic_generation():
    """Test basic LLM generation with tier tracking."""
    print("=== Test 1: Basic Generation ===")
    client = LLMClient()
    
    # Test flash tier (default)
    text, usage, tier = client.generate(
        "You are a helpful assistant.",
        "Say 'Hello' in one word.",
        tier="flash"
    )
    print(f"Response: {text}")
    print(f"Tier used: {tier}")
    print(f"Usage stats: {usage.get('quota_stats')}")
    print()

@pytest.mark.skipif(not SETTINGS.gemini_api_key, reason="API key required")
@pytest.mark.integration
def test_quota_stats():
    """Test quota tracking."""
    print("=== Test 2: Quota Stats ===")
    stats = MODEL_MANAGER.get_stats()
    print(f"Current usage: {stats}")
    print()

@pytest.mark.integration
def test_model_selection():
    """Test model tier selection."""
    print("=== Test 3: Model Selection ===")
    
    # Test each tier
    for tier in ["lite", "flash", "pro"]:
        model, actual_tier = MODEL_MANAGER.get_available_model(tier)
        print(f"Requested: {tier}, Got: {actual_tier}, Model: {model}")
    print()

if __name__ == "__main__":
    test_model_selection()
    test_basic_generation()
    test_quota_stats()
    print("✓ All tests passed!")
