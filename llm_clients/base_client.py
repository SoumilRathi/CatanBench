"""
Base class for LLM clients.

This module defines the interface that all LLM clients must implement
to work with the CatanBench system.
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


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
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the model being used.
        
        Returns:
            Dictionary containing model information
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