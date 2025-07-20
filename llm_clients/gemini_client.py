"""
Google Gemini client for CatanBench.

This module provides integration with Google's Gemini models including
Gemini Pro and Ultra variants.
"""

import os
import time
from typing import Dict, Any, Optional

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from .base_client import BaseLLMClient, LLMClientError


class GeminiClient(BaseLLMClient):
    """
    Google Gemini client implementation.
    
    Supports Gemini Pro and other Google generative AI models.
    """
    
    # Token costs per 1M tokens (as of 2024 - may need updating)
    TOKEN_COSTS = {
        "gemini-pro": {"input": 0.5, "output": 1.5},
        "gemini-1.5-pro": {"input": 3.5, "output": 10.5},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.3},
    }
    
    def __init__(
        self, 
        model_name: str = "gemini-1.5-flash", 
        api_key: Optional[str] = None
    ):
        """
        Initialize the Gemini client.
        
        Args:
            model_name: Gemini model name
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
        """
        if not GOOGLE_AVAILABLE:
            raise ImportError("Google Generative AI library not available. Install with: pip install google-generativeai")
        
        super().__init__(model_name, api_key)
        
        # Configure Google Generative AI
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Google API key not provided. Set GOOGLE_API_KEY environment variable or pass api_key parameter.")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
    
    def query(
        self, 
        prompt: str, 
        temperature: float = 0.1, 
        max_tokens: Optional[int] = None,
        timeout: float = 30.0,
        **kwargs
    ) -> str:
        """
        Query Gemini model.
        
        Args:
            prompt: Input prompt
            temperature: Response randomness (0.0-2.0)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            **kwargs: Additional Gemini parameters
            
        Returns:
            Generated response text
            
        Raises:
            LLMClientError: If the request fails
        """
        start_time = time.time()
        
        try:
            # Prepare generation configuration
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                **kwargs
            )
            
            # Make API request
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Extract response text
            if not response.parts:
                raise LLMClientError("Empty response from Gemini", "EMPTY_RESPONSE")
            
            response_text = response.text
            
            # Calculate costs and update stats (note: Gemini doesn't provide usage info in all cases)
            response_time = time.time() - start_time
            tokens_used = self._estimate_tokens(prompt + response_text)  # Rough estimate
            cost = self._calculate_cost_estimate(tokens_used)
            
            self._update_stats(response_time, success=True, tokens_used=tokens_used, cost=cost)
            
            return response_text
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            
            # Handle specific Google API errors
            if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                raise LLMClientError(f"Gemini rate limit exceeded: {e}", "RATE_LIMIT", e)
            elif "timeout" in str(e).lower():
                raise LLMClientError(f"Gemini request timeout: {e}", "TIMEOUT", e)
            else:
                raise LLMClientError(f"Gemini API error: {e}", "API_ERROR", e)
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a text string.
        
        This is a rough approximation since we don't have exact tokenization.
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        # Rough approximation: ~4 characters per token for English text
        return len(text) // 4
    
    def _calculate_cost_estimate(self, tokens_used: int) -> float:
        """
        Estimate the cost based on token usage.
        
        Args:
            tokens_used: Estimated token count
            
        Returns:
            Estimated cost in USD
        """
        if self.model_name not in self.TOKEN_COSTS:
            return 0.0
        
        costs = self.TOKEN_COSTS[self.model_name]
        # Assume 50/50 split between input and output tokens
        input_tokens = tokens_used // 2
        output_tokens = tokens_used - input_tokens
        
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        
        return input_cost + output_cost
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the Gemini model."""
        return {
            "provider": "Google",
            "model": self.model_name,
            "supports_json_mode": False,  # Gemini supports JSON through prompting
            "context_length": self._get_context_length(),
            "cost_per_1m_input": self.TOKEN_COSTS.get(self.model_name, {}).get("input", 0.0),
            "cost_per_1m_output": self.TOKEN_COSTS.get(self.model_name, {}).get("output", 0.0)
        }
    
    def _get_context_length(self) -> int:
        """Get the context length for the model."""
        context_lengths = {
            "gemini-pro": 32768,
            "gemini-1.5-pro": 1048576,  # 1M tokens
            "gemini-1.5-flash": 1048576,  # 1M tokens
        }
        return context_lengths.get(self.model_name, 32768)
    
    def query_with_safety_settings(
        self, 
        prompt: str, 
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: float = 30.0,
        safety_settings: Optional[Dict] = None
    ) -> str:
        """
        Query Gemini with custom safety settings.
        
        Args:
            prompt: Input prompt
            temperature: Response randomness
            max_tokens: Maximum tokens to generate
            timeout: Request timeout
            safety_settings: Custom safety settings
            
        Returns:
            Generated response text
        """
        start_time = time.time()
        
        try:
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens
            )
            
            # Set up safety settings if provided
            safety_settings_config = None
            if safety_settings:
                safety_settings_config = [
                    {"category": category, "threshold": threshold}
                    for category, threshold in safety_settings.items()
                ]
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings_config
            )
            
            response_text = response.text
            
            # Update stats
            response_time = time.time() - start_time
            tokens_used = self._estimate_tokens(prompt + response_text)
            cost = self._calculate_cost_estimate(tokens_used)
            
            self._update_stats(response_time, success=True, tokens_used=tokens_used, cost=cost)
            
            return response_text
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"Error with Gemini safety settings query: {e}", "UNKNOWN", e)