"""
Refinement Service
------------------
LLM-based curation and refinement of collected items.
"""

import os
import json
from typing import Dict, Optional, List
from datetime import datetime

from scripts.config import config


class RefinementService:
    """Service for refining collected items using LLM-based curation."""
    
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize refinement service.
        
        Args:
            model: Model to use (e.g., "claude-3-5-sonnet-20241022" or Ollama model name)
            api_key: API key for external services (Anthropic, OpenAI, etc.)
        """
        self.model = model or os.getenv("REFINEMENT_MODEL", "claude-3-5-sonnet-20241022")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.use_ollama = self.model.startswith("mistral") or self.model.startswith("llama") or ":" in self.model
        
    def refine_item(self, item: Dict) -> Optional[Dict]:
        """
        Refine a single item using the ruthless curator prompt.
        
        Args:
            item: Raw item from collector
            
        Returns:
            Refined item with curation results, or None if item should be SKIPped
        """
        prompt = self._build_curator_prompt(item)
        
        if self.use_ollama:
            result = self._refine_with_ollama(prompt)
        else:
            result = self._refine_with_api(prompt)
        
        if not result or result.get("action") == "SKIP":
            return None
        
        # Build refined item
        refined = {
            "title": item.get("title", ""),
            "summary": result.get("summary", ""),
            "permanence": result.get("permanence", 0),
            "entities": result.get("entities", ""),
            "tags": result.get("tags", []),
            "source_url": item.get("url", ""),
            "source": item.get("source", ""),
            "published_at": item.get("published_at"),
            "content": item.get("content", "")[:3000],  # Limit content length
            "refined_at": datetime.now().isoformat(),
            "confidence": result.get("confidence", "medium"),
        }
        
        # Only return if permanence >= 8
        if refined["permanence"] < 8:
            return None
        
        return refined
    
    def _build_curator_prompt(self, item: Dict) -> str:
        """Build the ruthless curator prompt."""
        title = item.get("title", "")
        content = (item.get("content") or item.get("content_snippet", ""))[:6000]
        
        prompt = f"""You are a ruthless knowledge curator for a frontier-model-tier RAG system.

Input: a raw document titled "{title}" with content snippet: "{content}"

Tasks:
1. Is this actually new, non-obvious signal about frontier AI capabilities, safety, scaling laws, leaks, evals, or techniques? Yes/No
2. If No → output ONLY the word SKIP
3. If Yes → output JSON only with keys:
   - summary (one ultra-dense sentence)
   - permanence (1–10, where 10 = will matter in 2 years)
   - entities (comma-separated: models, companies, people)
   - tags (max 4, array)
   - confidence (high/medium/low)

Be extremely strict — skip 98% of items."""
        
        return prompt
    
    def _refine_with_ollama(self, prompt: str) -> Optional[Dict]:
        """Refine using Ollama."""
        try:
            import requests
            
            ollama_url = config.OLLAMA_API_BASE.replace("/api", "") + "/api/generate"
            response = requests.post(
                ollama_url,
                json={
                    "model": config.OLLAMA_CHAT_MODEL,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=120,
            )
            
            if response.status_code == 200:
                result_text = response.json().get("response", "")
                return self._parse_curator_response(result_text)
        except Exception as e:
            print(f"[WARN] Ollama refinement failed: {e}")
        
        return None
    
    def _refine_with_api(self, prompt: str) -> Optional[Dict]:
        """Refine using Anthropic API."""
        if not self.api_key:
            print("[WARN] No API key configured for refinement")
            return None
        
        try:
            import requests
            
            # Use Anthropic API
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 500,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                },
                timeout=120,
            )
            
            if response.status_code == 200:
                result_text = response.json()["content"][0]["text"]
                return self._parse_curator_response(result_text)
        except Exception as e:
            print(f"[WARN] API refinement failed: {e}")
        
        return None
    
    def _parse_curator_response(self, text: str) -> Optional[Dict]:
        """Parse the curator's response."""
        text = text.strip()
        
        # Check for SKIP
        if "SKIP" in text.upper():
            return {"action": "SKIP"}
        
        # Try to parse JSON
        try:
            # Extract JSON from text (might be wrapped in markdown code blocks)
            if "```json" in text:
                json_start = text.find("```json") + 7
                json_end = text.find("```", json_start)
                json_text = text[json_start:json_end].strip()
            elif "```" in text:
                json_start = text.find("```") + 3
                json_end = text.find("```", json_start)
                json_text = text[json_start:json_end].strip()
            else:
                json_text = text
            
            # Try to find JSON object
            if "{" in json_text:
                json_start = json_text.find("{")
                json_end = json_text.rfind("}") + 1
                json_text = json_text[json_start:json_end]
            
            result = json.loads(json_text)
            result["action"] = "KEEP"
            return result
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract key fields
            if "permanence" in text.lower():
                # Try to extract permanence score
                import re
                permanence_match = re.search(r'permanence[:\s]+(\d+)', text, re.IGNORECASE)
                if permanence_match:
                    permanence = int(permanence_match.group(1))
                    if permanence >= 8:
                        return {
                            "action": "KEEP",
                            "permanence": permanence,
                            "summary": text[:200],
                            "entities": "",
                            "tags": [],
                            "confidence": "medium",
                        }
        
        return {"action": "SKIP"}

