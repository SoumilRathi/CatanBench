"""
OpenAI GPT client for CatanBench.

This module provides integration with OpenAI's GPT models including
GPT-4, GPT-3.5-turbo, and other variants.
"""

import os
import time
from typing import Dict, Any, Optional

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .base_client import BaseLLMClient, LLMClientError


class OpenAIClient(BaseLLMClient):
    """
    OpenAI GPT client implementation.
    
    Supports GPT-4, GPT-3.5-turbo, and other OpenAI models with
    proper error handling, rate limiting, and cost tracking.
    """
    
    # Token costs per 1K tokens (as of 2024 - may need updating)
    TOKEN_COSTS = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
    }
    
    def __init__(
        self, 
        model_name: str = "gpt-4o", 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None
    ):
        """
        Initialize the OpenAI client.
        
        Args:
            model_name: OpenAI model name (e.g., "gpt-4", "gpt-3.5-turbo")
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            base_url: Custom base URL for API requests
            organization: OpenAI organization ID
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not available. Install with: pip install openai")
        
        super().__init__(model_name, api_key)
        
        # Set up OpenAI client
        self.client = openai.OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url,
            organization=organization
        )
        
        if not self.client.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
    
    def query(
        self, 
        prompt: str, 
        temperature: float = 0.1, 
        max_tokens: Optional[int] = None,
        timeout: float = 30.0,
        **kwargs
    ) -> str:
        """
        Query OpenAI GPT model.
        
        Args:
            prompt: Input prompt
            temperature: Response randomness (0.0-2.0)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            **kwargs: Additional OpenAI parameters
            
        Returns:
            Generated response text
            
        Raises:
            LLMClientError: If the request fails
        """
        start_time = time.time()
        
        try:
            # Prepare request parameters
            request_params = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "timeout": timeout,
                **kwargs
            }
            
            if max_tokens is not None:
                request_params["max_tokens"] = max_tokens
            
            # Make API request
            response = self.client.chat.completions.create(**request_params)
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Calculate costs and update stats
            response_time = time.time() - start_time
            tokens_used = response.usage.total_tokens if response.usage else 0
            cost = self._calculate_cost(response.usage) if response.usage else 0.0
            
            self._update_stats(response_time, success=True, tokens_used=tokens_used, cost=cost)
            
            return response_text or ""
            
        except openai.RateLimitError as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"OpenAI rate limit exceeded: {e}", "RATE_LIMIT", e)
            
        except openai.APITimeoutError as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"OpenAI request timeout: {e}", "TIMEOUT", e)
            
        except openai.APIError as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"OpenAI API error: {e}", "API_ERROR", e)
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"Unexpected error with OpenAI: {e}", "UNKNOWN", e)
    
    def _calculate_cost(self, usage) -> float:
        """
        Calculate the cost of a request based on token usage.
        
        Args:
            usage: OpenAI usage object
            
        Returns:
            Cost in USD
        """
        if not usage or self.model_name not in self.TOKEN_COSTS:
            return 0.0
        
        costs = self.TOKEN_COSTS[self.model_name]
        input_cost = (usage.prompt_tokens / 1000) * costs["input"]
        output_cost = (usage.completion_tokens / 1000) * costs["output"]
        
        return input_cost + output_cost
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the OpenAI model."""
        return {
            "provider": "OpenAI",
            "model": self.model_name,
            "supports_json_mode": self.model_name in ["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-3.5-turbo"],
            "context_length": self._get_context_length(),
            "cost_per_1k_input": self.TOKEN_COSTS.get(self.model_name, {}).get("input", 0.0),
            "cost_per_1k_output": self.TOKEN_COSTS.get(self.model_name, {}).get("output", 0.0)
        }
    
    def _get_context_length(self) -> int:
        """Get the context length for the model."""
        context_lengths = {
            "gpt-4": 8192,
            "gpt-4-turbo": 128000,
            "gpt-4o": 128000,
            "gpt-3.5-turbo": 4096,
        }
        return context_lengths.get(self.model_name, 4096)
    
    def query_with_json_mode(
        self, 
        prompt: str, 
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: float = 30.0
    ) -> str:
        """
        Query with JSON mode enabled (for supported models).
        
        Args:
            prompt: Input prompt
            temperature: Response randomness  
            max_tokens: Maximum tokens to generate
            timeout: Request timeout
            
        Returns:
            JSON-formatted response
        """
        if not self.get_model_info()["supports_json_mode"]:
            # Fallback to regular query with JSON instruction
            json_prompt = f"{prompt}\n\nPlease respond with valid JSON only."
            return self.query(json_prompt, temperature, max_tokens, timeout)
        
        return self.query(
            prompt, 
            temperature, 
            max_tokens, 
            timeout,
            response_format={"type": "json_object"}
        )