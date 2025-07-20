"""
Anthropic Claude client for CatanBench.

This module provides integration with Anthropic's Claude models including
Claude 3 Haiku, Sonnet, and Opus variants.
"""

import os
import time
from typing import Dict, Any, Optional

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from .base_client import BaseLLMClient, LLMClientError


class ClaudeClient(BaseLLMClient):
    """
    Anthropic Claude client implementation.
    
    Supports Claude 3 models (Haiku, Sonnet, Opus) with proper error
    handling, rate limiting, and cost tracking.
    """
    
    # Token costs per 1M tokens (as of 2024 - may need updating)
    TOKEN_COSTS = {
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},
        "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        "claude-3-5-haiku-20241022": {"input": 1.0, "output": 5.0},
    }
    
    def __init__(
        self, 
        model_name: str = "claude-3-5-sonnet-20241022", 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize the Claude client.
        
        Args:
            model_name: Claude model name 
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            base_url: Custom base URL for API requests
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic library not available. Install with: pip install anthropic")
        
        super().__init__(model_name, api_key)
        
        # Set up Anthropic client
        client_kwargs = {
            "api_key": api_key or os.getenv("ANTHROPIC_API_KEY")
        }
        if base_url:
            client_kwargs["base_url"] = base_url
            
        self.client = anthropic.Anthropic(**client_kwargs)
        
        if not self.client.api_key:
            raise ValueError("Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")
    
    def query(
        self, 
        prompt: str, 
        temperature: float = 0.1, 
        max_tokens: Optional[int] = None,
        timeout: float = 30.0,
        **kwargs
    ) -> str:
        """
        Query Claude model.
        
        Args:
            prompt: Input prompt
            temperature: Response randomness (0.0-1.0)
            max_tokens: Maximum tokens to generate (defaults to 4096)
            timeout: Request timeout in seconds
            **kwargs: Additional Anthropic parameters
            
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
                "max_tokens": max_tokens or 4096,
                "timeout": timeout,
                **kwargs
            }
            
            # Make API request
            response = self.client.messages.create(**request_params)
            
            # Extract response text
            response_text = ""
            for content in response.content:
                if content.type == "text":
                    response_text += content.text
            
            # Calculate costs and update stats
            response_time = time.time() - start_time
            tokens_used = response.usage.input_tokens + response.usage.output_tokens if response.usage else 0
            cost = self._calculate_cost(response.usage) if response.usage else 0.0
            
            self._update_stats(response_time, success=True, tokens_used=tokens_used, cost=cost)
            
            return response_text
            
        except anthropic.RateLimitError as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"Claude rate limit exceeded: {e}", "RATE_LIMIT", e)
            
        except anthropic.APITimeoutError as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"Claude request timeout: {e}", "TIMEOUT", e)
            
        except anthropic.APIError as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"Claude API error: {e}", "API_ERROR", e)
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"Unexpected error with Claude: {e}", "UNKNOWN", e)
    
    def _calculate_cost(self, usage) -> float:
        """
        Calculate the cost of a request based on token usage.
        
        Args:
            usage: Anthropic usage object
            
        Returns:
            Cost in USD
        """
        if not usage or self.model_name not in self.TOKEN_COSTS:
            return 0.0
        
        costs = self.TOKEN_COSTS[self.model_name]
        input_cost = (usage.input_tokens / 1_000_000) * costs["input"]
        output_cost = (usage.output_tokens / 1_000_000) * costs["output"]
        
        return input_cost + output_cost
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the Claude model."""
        return {
            "provider": "Anthropic",
            "model": self.model_name,
            "supports_json_mode": False,  # Claude doesn't have explicit JSON mode
            "context_length": self._get_context_length(),
            "cost_per_1m_input": self.TOKEN_COSTS.get(self.model_name, {}).get("input", 0.0),
            "cost_per_1m_output": self.TOKEN_COSTS.get(self.model_name, {}).get("output", 0.0)
        }
    
    def _get_context_length(self) -> int:
        """Get the context length for the model."""
        # Most Claude 3 models support 200k tokens
        return 200_000
    
    def query_with_system_message(
        self, 
        system_message: str,
        user_message: str, 
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: float = 30.0
    ) -> str:
        """
        Query Claude with separate system and user messages.
        
        Args:
            system_message: System/instruction message
            user_message: User prompt message
            temperature: Response randomness
            max_tokens: Maximum tokens to generate
            timeout: Request timeout
            
        Returns:
            Generated response text
        """
        start_time = time.time()
        
        try:
            request_params = {
                "model": self.model_name,
                "system": system_message,
                "messages": [
                    {"role": "user", "content": user_message}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
                "timeout": timeout
            }
            
            response = self.client.messages.create(**request_params)
            
            # Extract response text
            response_text = ""
            for content in response.content:
                if content.type == "text":
                    response_text += content.text
            
            # Calculate costs and update stats
            response_time = time.time() - start_time
            tokens_used = response.usage.input_tokens + response.usage.output_tokens if response.usage else 0
            cost = self._calculate_cost(response.usage) if response.usage else 0.0
            
            self._update_stats(response_time, success=True, tokens_used=tokens_used, cost=cost)
            
            return response_text
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"Error with Claude system message query: {e}", "UNKNOWN", e)