"""
LLM clients for CatanBench competition.

This module contains clients for GPT-5, Gemini 2.5 Pro, Claude Sonnet 4, and Kimi K2.
"""

import os
import time
from typing import Optional
from dotenv import load_dotenv

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

# Base client interface and error moved here from llm_clients/base_client.py
# to centralize client implementations in a single module.
import time
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseLLMClient(ABC):
    """
    Abstract base class for all LLM clients.
    
    This class defines the interface that must be implemented by all
    LLM clients to ensure consistent behavior across different providers.
    """
    
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        """
        Initialize the LLM client.
        
        Args:
            model_name: Name/identifier of the model to use
            api_key: API key for authentication (if required)
        """
        self.model_name = model_name
        self.api_key = api_key
        
        # Performance tracking
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "avg_response_time": 0.0,
            "total_tokens_used": 0,
            "total_cost": 0.0
        }
    
    @abstractmethod
    def query(
        self, 
        prompt: str, 
        temperature: float = 0.1, 
        max_tokens: Optional[int] = None,
        timeout: float = 30.0,
        **kwargs
    ) -> str:
        """
        Query the LLM with a prompt.
        
        Args:
            prompt: The input prompt to send to the LLM
            temperature: Temperature for response randomness (0.0-1.0)
            max_tokens: Maximum tokens to generate (None for model default)
            timeout: Request timeout in seconds
            **kwargs: Additional provider-specific parameters
            
        Returns:
            The LLM's response as a string
            
        Raises:
            LLMClientError: If the request fails
        """
        pass
    
    def _update_stats(
        self, 
        response_time: float, 
        success: bool, 
        tokens_used: int = 0, 
        cost: float = 0.0
    ):
        """
        Update internal statistics after a request.
        
        Args:
            response_time: Time taken for the request in seconds
            success: Whether the request was successful
            tokens_used: Number of tokens used in the request
            cost: Cost of the request in USD
        """
        self.stats["total_requests"] += 1
        self.stats["total_response_time"] += response_time
        self.stats["avg_response_time"] = (
            self.stats["total_response_time"] / self.stats["total_requests"]
        )
        self.stats["total_tokens_used"] += tokens_used
        self.stats["total_cost"] += cost
        
        if success:
            self.stats["successful_requests"] += 1
        else:
            self.stats["failed_requests"] += 1
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for this client.
        
        Returns:
            Dictionary containing performance metrics
        """
        return {
            "model_name": self.model_name,
            "total_requests": self.stats["total_requests"],
            "success_rate": (
                self.stats["successful_requests"] / max(1, self.stats["total_requests"]) 
            ),
            "avg_response_time": self.stats["avg_response_time"],
            "total_tokens_used": self.stats["total_tokens_used"],
            "total_cost": self.stats["total_cost"],
            "avg_tokens_per_request": (
                self.stats["total_tokens_used"] / max(1, self.stats["total_requests"]) 
            ),
            "avg_cost_per_request": (
                self.stats["total_cost"] / max(1, self.stats["total_requests"]) 
            )
        }
    
    def reset_stats(self):
        """Reset performance statistics."""
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "avg_response_time": 0.0,
            "total_tokens_used": 0,
            "total_cost": 0.0
        }
    
    def __repr__(self):
        return f"{self.__class__.__name__}({self.model_name})"


class LLMClientError(Exception):
    """Exception raised when LLM client operations fail."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.error_code = error_code
        self.original_error = original_error

load_dotenv(".env", override=True)


class GPT5Client(BaseLLMClient):
    """OpenAI GPT-5 client."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("gpt-5", api_key)
        
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not available. Install with: pip install openai")
        
        self.client = openai.OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY")
        )
        
        if not self.client.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable.")
    
    def query(self, prompt: str, temperature: float = 0.1, max_tokens: Optional[int] = None, timeout: float = 30.0, **kwargs) -> str:
        start_time = time.time()
        
        try:
            request_params = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                **kwargs
            }
            
            if max_tokens is not None:
                request_params["max_tokens"] = max_tokens
            
            response = self.client.chat.completions.create(**request_params)
            response_text = response.choices[0].message.content
            
            response_time = time.time() - start_time
            tokens_used = response.usage.total_tokens if response.usage else 0
            self._update_stats(response_time, success=True, tokens_used=tokens_used, cost=0.0)
            
            return response_text or ""
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"GPT-5 error: {e}", "API_ERROR", e)


class ClaudeSonnet4Client(BaseLLMClient):
    """Anthropic Claude Sonnet 4 client."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("claude-sonnet-4-20250514", api_key)
        
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic library not available. Install with: pip install anthropic")
        
        self.client = anthropic.Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        )
        
        if not self.client.api_key:
            raise ValueError("Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable.")
    
    def query(self, prompt: str, temperature: float = 0.1, max_tokens: Optional[int] = None, timeout: float = 30.0, **kwargs) -> str:
        start_time = time.time()
        
        try:
            request_params = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens or 4096,
                "timeout": timeout,
                **kwargs
            }
            
            response = self.client.messages.create(**request_params)
            
            response_text = ""
            for content in response.content:
                if content.type == "text":
                    response_text += content.text
            
            response_time = time.time() - start_time
            tokens_used = response.usage.input_tokens + response.usage.output_tokens if response.usage else 0
            self._update_stats(response_time, success=True, tokens_used=tokens_used, cost=0.0)
            
            return response_text
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"Claude Sonnet 4 error: {e}", "API_ERROR", e)


class Gemini25ProClient(BaseLLMClient):
    """Google Gemini 2.5 Pro client."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("gemini-2.5-pro", api_key)
        
        if not GOOGLE_AVAILABLE:
            raise ImportError("Google Generative AI library not available. Install with: pip install google-generativeai")
        
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Google API key not provided. Set GOOGLE_API_KEY environment variable.")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.model_name)
    
    def query(self, prompt: str, temperature: float = 0.1, max_tokens: Optional[int] = None, timeout: float = 30.0, **kwargs) -> str:
        start_time = time.time()
        
        try:
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                **kwargs
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            if not response.parts:
                raise LLMClientError("Empty response from Gemini 2.5 Pro", "EMPTY_RESPONSE")
            
            response_text = response.text
            
            response_time = time.time() - start_time
            tokens_used = len(prompt + response_text) // 4  # Rough estimate
            self._update_stats(response_time, success=True, tokens_used=tokens_used, cost=0.0)
            
            return response_text
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"Gemini 2.5 Pro error: {e}", "API_ERROR", e)


class KimiK2Client(BaseLLMClient):
    """Kimi K2 client via OpenRouter."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("moonshotai/kimi-k2", api_key)  # Kimi K2 model on OpenRouter
        
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not available. Install with: pip install openai")
        
        self.client = openai.OpenAI(
            api_key=api_key or os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
        
        if not self.client.api_key:
            raise ValueError("OpenRouter API key not provided. Set OPENROUTER_API_KEY environment variable.")
    
    def query(self, prompt: str, temperature: float = 0.1, max_tokens: Optional[int] = None, timeout: float = 30.0, **kwargs) -> str:
        start_time = time.time()
        
        try:
            request_params = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "timeout": timeout,
                **kwargs
            }
            
            if max_tokens is not None:
                request_params["max_tokens"] = max_tokens
            
            response = self.client.chat.completions.create(**request_params)
            response_text = response.choices[0].message.content
            
            response_time = time.time() - start_time
            tokens_used = response.usage.total_tokens if response.usage else 0
            self._update_stats(response_time, success=True, tokens_used=tokens_used, cost=0.0)
            
            return response_text or ""
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(response_time, success=False)
            raise LLMClientError(f"Kimi K2 (OpenRouter) error: {e}", "API_ERROR", e)


# Compatibility wrappers to preserve existing example/test imports
class OpenAIClient(GPT5Client):
    """Generic OpenAI chat client. Defaults to a cost-efficient model."""
    
    def __init__(self, model_name: str = "gpt-4o-mini", api_key: Optional[str] = None):
        super().__init__(api_key=api_key)
        # Override the default model with caller-provided one
        self.model_name = model_name


class ClaudeClient(ClaudeSonnet4Client):
    """Generic Anthropic Claude client."""
    
    def __init__(self, model_name: str = "claude-3-5-haiku-20241022", api_key: Optional[str] = None):
        super().__init__(api_key=api_key)
        self.model_name = model_name


class GeminiClient(Gemini25ProClient):
    """Generic Google Gemini client."""
    
    def __init__(self, model_name: str = "gemini-1.5-flash", api_key: Optional[str] = None):
        super().__init__(api_key=api_key)
        self.model_name = model_name
        if GOOGLE_AVAILABLE:
            # Recreate the model with the new model name
            self.model = genai.GenerativeModel(self.model_name)