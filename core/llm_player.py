"""
LLM-based player for Catan using the Catanatron library.

This module provides the base LLMPlayer class that integrates with various
LLM clients to make strategic decisions in Settlers of Catan.
"""

import traceback
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional

from catanatron.models.player import Player
from catanatron.models.enums import Action, ActionType

from .game_state import GameStateExtractor
from .action_parser import ActionParser
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))



class LLMPlayer(Player):
    """
    Base class for LLM-powered Catan players.
    
    This class handles the interaction between the Catanatron game engine
    and various LLM clients, providing game state extraction, prompt
    generation, and action parsing.
    """
    
    def __init__(
        self, 
        color, 
        llm_client, 
        name: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
        timeout: float = 30.0,
        is_bot: bool = True
    ):
        """
        Initialize the LLM player.
        
        Args:
            color: Player color from catanatron.models.player.Color
            llm_client: LLM client instance (must implement query method)
            name: Optional name for the player (defaults to LLM model name)
            temperature: Temperature for LLM responses (0.0-1.0)
            max_retries: Maximum retry attempts for failed LLM calls
            timeout: Timeout in seconds for LLM responses
            is_bot: Whether this is a bot player
        """
        super().__init__(color, is_bot)
        self.llm_client = llm_client
        self.name = name or f"{llm_client.model_name}_{color.value}"
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout
        
        # Initialize helper components
        self.game_state_extractor = GameStateExtractor()
        self.action_parser = ActionParser(self.game_state_extractor.hex_mapper)
        
        # Statistics tracking
        self.stats = {
            "total_decisions": 0,
            "successful_decisions": 0,
            "failed_decisions": 0,
            "avg_decision_time": 0.0,
            "total_decision_time": 0.0,
            "retry_count": 0,
            "fallback_count": 0
        }
        
        # Logging setup
        self.logger = logging.getLogger(f"LLMPlayer.{self.name}")
        
    def decide(self, game, playable_actions: List[Action]) -> Action:
        """
        Main decision-making method called by Catanatron.
        
        Args:
            game: Current game state (read-only)
            playable_actions: List of valid actions to choose from
            
        Returns:
            Selected Action from playable_actions
        """
        start_time = time.time()
        self.stats["total_decisions"] += 1

        if (len(playable_actions) == 1) and ((playable_actions[0].action_type == ActionType.ROLL) or (playable_actions[0].action_type == ActionType.END_TURN)):
            print(self.name, "selected action: ", playable_actions[0].action_type, "in", 0, "seconds")
            self.logger.info(f"Selected action: {playable_actions[0].action_type} in {0:.2f}s")
            return playable_actions[0]
        
        try:
            # Extract game state information
            game_state = self.game_state_extractor.extract_state(game, self.color)
            
            # Convert actions to descriptions (this also registers mappings)
            self.action_parser.describe_actions(playable_actions)
            
            # Get readable descriptions for the prompt
            action_descriptions = self.action_parser.get_readable_action_descriptions(playable_actions)
            
            # Create prompt for LLM
            prompt = self._create_decision_prompt(game_state, action_descriptions)

            # print(prompt)
            
            # Query LLM with retry logic
            selected_action = self._query_llm_with_retry(prompt, playable_actions)
            
            # Update statistics
            decision_time = time.time() - start_time
            self._update_stats(decision_time, success=True)

            print(self.name, "selected action: ", selected_action.action_type, "in", decision_time, "seconds")
            
            self.logger.info(f"Selected action: {selected_action.action_type} in {decision_time:.2f}s")
            return selected_action
            
        except Exception as e:
            # Ultra-safe fallback - catch ANY exception and use first action
            tb = traceback.format_exc()
            self.logger.error(f"LLM decision failed: {e}")
            self.logger.error(f"Full traceback:\n{tb}")
            self.logger.warning(f"Available actions: {[a.action_type for a in playable_actions]}")
            decision_time = time.time() - start_time
            self._update_stats(decision_time, success=False)
            fallback_action = self._fallback_action(playable_actions)
            print(f"{self.name} FALLBACK selected action: {fallback_action.action_type} in {decision_time:.2f}s")
            return fallback_action
    
    def _create_decision_prompt(self, game_state: Dict[str, Any], action_descriptions: Dict[int, str]) -> str:
        """
        Create the main decision-making prompt for the LLM.
        
        Args:
            game_state: Extracted game state information
            action_descriptions: Mapping of action indices to descriptions
            
        Returns:
            Formatted prompt string
        """
        from prompts.system_prompts import get_system_prompt, game_state_to_prompt
        from prompts.action_templates import get_decision_template
        
        system_prompt = get_system_prompt()
        decision_template = get_decision_template()
        game_state_prompt = game_state_to_prompt(game_state)
        
        # Format the prompt with game state and actions
        prompt = f"""{system_prompt}

CURRENT GAME STATE:
{game_state_prompt}

AVAILABLE ACTIONS:
{json.dumps(action_descriptions, indent=2)}

{decision_template}

You must respond with a JSON object containing:
{{"action_index": <integer>, "reasoning": "<explanation>"}}

Where action_index is the number/index of the action you want to take from the list above.
action_index must be an integer between 0 and {len(action_descriptions) - 1}, based on the index of the action in the list above.
"""
        return prompt
    
    def _query_llm_with_retry(self, prompt: str, playable_actions: List[Action]) -> Action:
        """
        Query the LLM with retry logic and error handling.
        
        Args:
            prompt: The prompt to send to the LLM
            playable_actions: List of valid actions
            
        Returns:
            Selected Action
            
        Raises:
            Exception: If all retries fail
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Query the LLM
                response = self.llm_client.query(
                    prompt,
                    temperature=self.temperature,
                    timeout=self.timeout
                )
                
                # Parse the response
                action_index, reasoning = self._parse_llm_response(response)
                
                # Validate action index
                if 0 <= action_index < len(playable_actions):
                    selected_action = playable_actions[action_index]
                    self.logger.debug(f"LLM reasoning: {reasoning}")
                    return selected_action
                else:
                    print(prompt, response, action_index, playable_actions)
                    raise ValueError(f"Invalid action index: {action_index}")
                    
            except Exception as e:
                last_error = e
                self.stats["retry_count"] += 1
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(0.5)  # Brief delay before retry
        
        raise Exception(f"All retry attempts failed. Last error: {last_error}")
    
    def use_groq(prompt, is_json=False, temperature=1):
        message_params = {  
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                },
            ],
            "temperature": temperature,
            "max_completion_tokens": 1024,
            "top_p": 1,
            "stream": False,
            "stop": None,
        }

        completion = groq_client.chat.completions.create(**message_params)

        response = completion.choices[0].message.content

        if is_json:
            # get the response between the first { and the last }
            response = response[response.find('{'):response.rfind('}')+1]
            print(response)
            response = json.loads(response)

        else:
            response = response.strip()

        return response

    def json_fix(self, input): 
        prompt = f"""
        You are a JSON fixer. 
        
        You have been given a piece of text that is not valid JSON. Extract the valid JSON from it and return it.
        
        Here is the text:
        {input}

        Return the valid JSON. Ensure you return perfect json with perfect indentation and no outside text.
        """

        response = self.use_groq(prompt)
        response = self.clean_json(response)
        return response
    

    def clean_json(self, json_str):
        json_start = None
        depth = 0
        json_end = json_str.rfind('}')
        for i in range(json_end, -1, -1):
            if json_str[i] == '}':
                depth += 1
            elif json_str[i] == '{':
                depth -= 1
                if depth == 0:  
                    json_start = i
                    break
        
        if json_start is not None:
            return json_str[json_start:json_end+1]
        else:
            return json_str
    
    def _parse_llm_response(self, response: str) -> tuple[int, str]:
        """
        Parse the LLM response to extract action index and reasoning.
        
        Args:
            response: Raw response from the LLM
            
        Returns:
            Tuple of (action_index, reasoning)
        """
        try:
            # Try to parse as JSON first
            try:
                response = self.clean_json(response)
                parsed = json.loads(response)
            except Exception as e:
                print(f"Error cleaning JSON: {e}")
                response = self.json_fix(response)
                parsed = json.loads(response)
            
            action_index = int(parsed.get("action_index"))
            reasoning = parsed.get("reasoning", "No reasoning provided")
            return action_index, reasoning
            
        except (json.JSONDecodeError, ValueError, TypeError):
            # Fallback: try to extract number from response
            import re
            numbers = re.findall(r'\b\d+\b', response)
            if numbers:
                action_index = int(numbers[0])
                return action_index, f"Extracted from: {response[:100]}..."
            else:
                raise ValueError(f"Could not parse response: {response}")
    
    def _fallback_action(self, playable_actions: List[Action]) -> Action:
        """
        Select a fallback action when LLM fails.
        
        Ultra-safe fallback that always returns the first valid action to prevent crashes.
        
        Args:
            playable_actions: List of valid actions
            
        Returns:
            Selected Action (always the first one to be safe)
        """
        self.stats["fallback_count"] += 1
        
        # Ultra-safe: always return the first action to prevent any crashes
        if not playable_actions:
            raise RuntimeError("No actions supplied to fallback!")
        
        # Always return the first action - this guarantees we never crash
        fallback_action = playable_actions[0]
        self.logger.warning(f"Using fallback action: {fallback_action.action_type}")
        return fallback_action
    
    def _update_stats(self, decision_time: float, success: bool):
        """Update internal statistics."""
        self.stats["total_decision_time"] += decision_time
        self.stats["avg_decision_time"] = (
            self.stats["total_decision_time"] / self.stats["total_decisions"]
        )
        
        if success:
            self.stats["successful_decisions"] += 1
        else:
            self.stats["failed_decisions"] += 1
    
    def reset_state(self):
        """Reset any state between games."""
        # Reset statistics for new game
        game_stats = self.stats.copy()
        self.stats = {
            "total_decisions": 0,
            "successful_decisions": 0,
            "failed_decisions": 0,
            "avg_decision_time": 0.0,
            "total_decision_time": 0.0,
            "retry_count": 0,
            "fallback_count": 0
        }
        return game_stats
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance statistics for this player."""
        total_decisions = self.stats["total_decisions"]
        if total_decisions == 0:
            return {"message": "No decisions made yet"}
            
        success_rate = self.stats["successful_decisions"] / total_decisions
        return {
            "player_name": self.name,
            "total_decisions": total_decisions,
            "success_rate": success_rate,
            "avg_decision_time": self.stats["avg_decision_time"],
            "retry_rate": self.stats["retry_count"] / total_decisions,
            "fallback_rate": self.stats["fallback_count"] / total_decisions
        }
    
    def __repr__(self):
        return f"LLMPlayer({self.name}:{self.color.value})"