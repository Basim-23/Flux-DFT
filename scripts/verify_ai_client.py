"""
Verify FluxAI Client.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

try:
    from fluxdft.ai import FluxAIClient, AIPrompts
    print("✓ Imported FluxAIClient and AIPrompts")
    
    client = FluxAIClient(api_key="", provider="openai")
    print(f"✓ Instantiated Client (Available: {client.is_available()})")
    
    if not client.is_available():
        print("  (Correctly unavailable without API key)")
        
    print("✓ verification passed")
    
except Exception as e:
    print(f"FAILED: {e}")
