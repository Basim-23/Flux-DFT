"""
FluxAI Core Client.
Handles interaction with LLM providers (e.g., OpenAI, Anthropic, or Local).
Enforces safety constraints (Text-only output, no code execution).
"""

import os
from typing import Optional, Dict, Any
from .prompts import AIPrompts

# Simple Mock for now, or real client if key exists
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

class FluxAIClient:
    """
    The trusted AI interface.
    """
    
    def __init__(self, api_key: str = "", provider: str = "openai", model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.provider = provider
        self.model = model
        self.enabled = bool(api_key)
        
        if HAS_OPENAI and self.api_key:
            openai.api_key = self.api_key
            
    def is_available(self) -> bool:
        """Check if AI service is configured and ready."""
        return self.enabled and HAS_OPENAI
        
    def query(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a strictly text-based query to the AI.
        Internal method - use specific role methods instead.
        """
        if not self.is_available():
            return "AI Assistant not configured. Please add API Key in settings."
            
        try:
            # call openai chat completion
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3, # Low temperature for factual consistency
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"AI Error: {str(e)}"

    # --- Role-Specific Methods ---
    
    def explain_physics(self, topic: str, context: Dict[str, Any]) -> str:
        """Role 1: Explain a physics concept or warning."""
        user_msg = AIPrompts.PHYSICS_EXPLAINER_USER.format(
            topic=topic,
            calc_type=context.get('calc_type', 'DFT'),
            material=context.get('formula', 'Material')
        )
        return self.query(AIPrompts.PHYSICS_EXPLAINER_SYS, user_msg)
        
    def analyze_error(self, log_snippet: str) -> str:
        """Role 2: Analyze a crash log."""
        user_msg = AIPrompts.ERROR_ANALYST_USER.format(
            log_snippet=log_snippet[-2000:] # Limit context
        )
        return self.query(AIPrompts.ERROR_ANALYST_SYS, user_msg)
        
    def draft_report(self, params: Dict[str, Any]) -> str:
        """Role 3: Draft methodology report."""
        user_msg = AIPrompts.REPORT_ASSISTANT_USER.format(
            functional=params.get('functional', 'PBE'),
            ecutwfc=params.get('ecutwfc', '?'),
            ecutrho=params.get('ecutrho', '?'),
            kpoints=params.get('kpoints', 'Automatic'),
            smearing=params.get('smearing', 'None')
        )
        return self.query(AIPrompts.REPORT_ASSISTANT_SYS, user_msg)
