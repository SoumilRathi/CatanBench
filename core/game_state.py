"""
Game state extraction for LLM players.

This module provides utilities to extract and serialize the Catan game state
into a format that LLMs can understand and reason about.
"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from catanatron.models.enums import RESOURCES, DEVELOPMENT_CARDS, ActionType, ActionPrompt
from catanatron.models.player import Color
from catanatron.state_functions import (
    get_player_buildings,
    player_key,
    player_num_resource_cards,
    player_has_rolled,
)


class GameStateExtractor:
    """
    Extracts and formats Catan game state for LLM consumption.
    
    Converts the complex internal game state into a structured,
    human-readable format that provides all necessary information
    for strategic decision-making.
    """
    
    def extract_state(self, game, current_player_color: Color) -> Dict[str, Any]:
        """
        Extract comprehensive game state information.
        
        Args:
            game: Catanatron Game object
            current_player_color: Color of the current player making decisions
            
        Returns:
            Dictionary containing all relevant game state information
        """
        state = game.state
        
        return {
            "game_info": self._extract_game_info(state),
            "board_state": self._extract_board_state(state),
            "current_player": self._extract_player_state(state, current_player_color, detailed=True),
            "opponents": self._extract_opponents_state(state, current_player_color),
            "resources_and_cards": self._extract_resources_info(state),
            "strategic_context": self._extract_strategic_context(state, current_player_color),
            "turn_context": self._extract_turn_context(state)
        }
    
    def _extract_game_info(self, state) -> Dict[str, Any]:
        """Extract basic game information."""
        return {
            "turn_number": getattr(state, 'num_turns', 0),
            "current_player_color": state.current_color().value,
            "winning_player": self._get_winning_player(state),
            "game_phase": self._determine_game_phase(state)
        }
    
    def _extract_board_state(self, state) -> Dict[str, Any]:
        """Extract board-related information."""
        board = state.board
        
        return {
            "robber_position": self._get_robber_position(board),
            "ports": self._extract_ports_info(board),
            "tiles": self._extract_tiles_info(board),
            "available_building_spots": self._get_available_building_spots(state),
            "longest_road_owner": self._get_longest_road_owner(state),
            "largest_army_owner": self._get_largest_army_owner(state)
        }
    
    def _extract_player_state(self, state, color: Color, detailed: bool = False) -> Dict[str, Any]:
        """Extract detailed state for a specific player."""
        player_state = state.player_state[player_key(state, color)]
        
        base_info = {
            "color": color.value,
            "victory_points": player_state.get("VICTORY_POINTS", 0),
            "public_victory_points": player_state.get("PUBLIC_VICTORY_POINTS", 0),
            "resource_cards_count": player_num_resource_cards(state, color),
            "development_cards_count": sum(
                player_state.get(f"{card}_IN_HAND", 0) 
                for card in DEVELOPMENT_CARDS
            ),
            "has_rolled_this_turn": player_has_rolled(state, color),
            "buildings": self._extract_buildings(state, color)
        }
        
        if detailed:
            # Include detailed resource and development card information for current player
            base_info.update({
                "resources": {
                    resource: player_state.get(resource, 0)
                    for resource in RESOURCES
                },
                "development_cards": {
                    card: {
                        "in_hand": player_state.get(f"{card}_IN_HAND", 0),
                        "played": player_state.get(f"{card}_PLAYED_THIS_TURN", 0)
                    }
                    for card in DEVELOPMENT_CARDS
                },
                "can_afford": self._check_affordability(state, color)
            })
        
        return base_info
    
    def _extract_opponents_state(self, state, current_player_color: Color) -> List[Dict[str, Any]]:
        """Extract state information for all opponents."""
        opponents = []
        all_colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
        
        for color in all_colors:
            if color != current_player_color:
                opponent_info = self._extract_player_state(state, color, detailed=False)
                opponents.append(opponent_info)
        
        return opponents
    
    def _extract_resources_info(self, state) -> Dict[str, Any]:
        """Extract information about resource availability and deck status."""
        return {
            "resource_bank": {
                resource: state.resource_freqdeck.get(resource, 0)
                for resource in RESOURCES
            },
            "development_cards_left": state.development_listdeck.count(),
            "dice_roll_this_turn": getattr(state, 'dice_roll', None)
        }
    
    def _extract_strategic_context(self, state, current_player_color: Color) -> Dict[str, Any]:
        """Extract strategic context and opportunities."""
        return {
            "trade_opportunities": self._identify_trade_opportunities(state, current_player_color),
            "building_priorities": self._suggest_building_priorities(state, current_player_color),
            "threat_assessment": self._assess_threats(state, current_player_color),
            "victory_analysis": self._analyze_victory_paths(state, current_player_color)
        }
    
    def _extract_turn_context(self, state) -> Dict[str, Any]:
        """Extract current turn context and phase."""
        return {
            "current_prompt": state.current_prompt.value if state.current_prompt else None,
            "expecting_action": self._get_expected_action_type(state),
            "turn_phase": self._determine_turn_phase(state)
        }
    
    def _extract_buildings(self, state, color: Color) -> Dict[str, Any]:
        """Extract building information for a player."""
        buildings = get_player_buildings(state, color)
        
        return {
            "settlements": list(buildings.get("settlements", [])),
            "cities": list(buildings.get("cities", [])),
            "roads": list(buildings.get("roads", [])),
            "settlements_available": 5 - len(buildings.get("settlements", [])),
            "cities_available": 4 - len(buildings.get("cities", [])),
            "roads_available": 15 - len(buildings.get("roads", []))
        }
    
    def _check_affordability(self, state, color: Color) -> Dict[str, bool]:
        """Check what the player can currently afford."""
        from catanatron.state_functions import (
            player_can_afford_dev_card,
            player_resource_freqdeck_contains
        )
        from catanatron.models.decks import (
            SETTLEMENT_COST_FREQDECK,
            CITY_COST_FREQDECK,
            ROAD_COST_FREQDECK
        )
        
        return {
            "settlement": player_resource_freqdeck_contains(state, color, SETTLEMENT_COST_FREQDECK),
            "city": player_resource_freqdeck_contains(state, color, CITY_COST_FREQDECK),
            "road": player_resource_freqdeck_contains(state, color, ROAD_COST_FREQDECK),
            "development_card": player_can_afford_dev_card(state, color)
        }
    
    def _get_robber_position(self, board) -> Optional[Tuple[int, int, int]]:
        """Get current robber position."""
        return getattr(board, 'robber_coordinate', None)
    
    def _extract_ports_info(self, board) -> List[Dict[str, Any]]:
        """Extract information about ports on the board."""
        ports = []
        if hasattr(board, 'map') and hasattr(board.map, 'port_nodes'):
            for node_id, port_resource in board.map.port_nodes.items():
                ports.append({
                    "node_id": node_id,
                    "resource": port_resource,
                    "trade_ratio": 2 if port_resource != "FOUR_TO_ONE" else 4
                })
        return ports
    
    def _extract_tiles_info(self, board) -> List[Dict[str, Any]]:
        """Extract tile information."""
        tiles = []
        if hasattr(board, 'map') and hasattr(board.map, 'tiles'):
            for coordinate, tile in board.map.tiles.items():
                tiles.append({
                    "coordinate": coordinate,
                    "resource": tile.resource,
                    "number": tile.number,
                    "has_robber": getattr(board, 'robber_coordinate', None) == coordinate
                })
        return tiles
    
    def _get_available_building_spots(self, state) -> Dict[str, List]:
        """Get available spots for building."""
        # This would require more detailed analysis of the board state
        # For now, return placeholder
        return {
            "settlement_spots": [],
            "city_upgrade_spots": [],
            "road_spots": []
        }
    
    def _identify_trade_opportunities(self, state, color: Color) -> List[Dict[str, Any]]:
        """Identify potential trading opportunities."""
        opportunities = []
        
        # Maritime trading opportunities
        player_resources = state.player_state[player_key(state, color)]
        for resource in RESOURCES:
            resource_count = player_resources.get(resource, 0)
            if resource_count >= 4:  # Can trade 4:1
                opportunities.append({
                    "type": "maritime",
                    "offer": resource,
                    "ratio": "4:1",
                    "available": True
                })
        
        return opportunities
    
    def _suggest_building_priorities(self, state, color: Color) -> List[str]:
        """Suggest building priorities based on current state."""
        priorities = []
        
        current_vp = state.player_state[player_key(state, color)].get("VICTORY_POINTS", 0)
        
        if current_vp < 5:
            priorities.extend(["settlements", "roads"])
        elif current_vp < 8:
            priorities.extend(["cities", "development_cards"])
        else:
            priorities.extend(["development_cards", "cities"])
        
        return priorities
    
    def _assess_threats(self, state, color: Color) -> List[Dict[str, Any]]:
        """Assess threats from opponents."""
        threats = []
        current_vp = state.player_state[player_key(state, color)].get("VICTORY_POINTS", 0)
        
        for opponent_color in [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]:
            if opponent_color != color:
                opponent_vp = state.player_state[player_key(state, opponent_color)].get("VICTORY_POINTS", 0)
                if opponent_vp >= current_vp + 2:
                    threats.append({
                        "player": opponent_color.value,
                        "threat_level": "high" if opponent_vp >= 8 else "medium",
                        "victory_points": opponent_vp
                    })
        
        return threats
    
    def _analyze_victory_paths(self, state, color: Color) -> Dict[str, Any]:
        """Analyze paths to victory."""
        current_vp = state.player_state[player_key(state, color)].get("VICTORY_POINTS", 0)
        vp_needed = 10 - current_vp
        
        return {
            "current_victory_points": current_vp,
            "points_needed": vp_needed,
            "turns_estimated": max(1, vp_needed // 2),  # Rough estimate
            "recommended_strategy": "aggressive" if vp_needed <= 3 else "building"
        }
    
    def _get_winning_player(self, state) -> Optional[str]:
        """Get winning player if game is over."""
        for color in [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]:
            vp = state.player_state[player_key(state, color)].get("VICTORY_POINTS", 0)
            if vp >= 10:
                return color.value
        return None
    
    def _determine_game_phase(self, state) -> str:
        """Determine what phase the game is in."""
        if state.current_prompt in [ActionPrompt.BUILD_INITIAL_SETTLEMENT, ActionPrompt.BUILD_INITIAL_ROAD]:
            return "setup"
        
        max_vp = max(
            state.player_state[player_key(state, color)].get("VICTORY_POINTS", 0)
            for color in [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
        )
        
        if max_vp < 5:
            return "early"
        elif max_vp < 8:
            return "mid"
        else:
            return "late"
    
    def _determine_turn_phase(self, state) -> str:
        """Determine the current phase within a turn."""
        if state.current_prompt == ActionPrompt.PLAY_TURN:
            if not player_has_rolled(state, state.current_color()):
                return "pre_roll"
            else:
                return "post_roll"
        elif state.current_prompt == ActionPrompt.DISCARD:
            return "discard"
        elif state.current_prompt == ActionPrompt.MOVE_ROBBER:
            return "move_robber"
        else:
            return str(state.current_prompt.value).lower()
    
    def _get_expected_action_type(self, state) -> Optional[str]:
        """Get the type of action expected based on current prompt."""
        prompt_to_action = {
            ActionPrompt.BUILD_INITIAL_SETTLEMENT: "BUILD_SETTLEMENT",
            ActionPrompt.BUILD_INITIAL_ROAD: "BUILD_ROAD",
            ActionPrompt.PLAY_TURN: "ROLL_OR_ACTION",
            ActionPrompt.DISCARD: "DISCARD",
            ActionPrompt.MOVE_ROBBER: "MOVE_ROBBER",
            ActionPrompt.DECIDE_TRADE: "TRADE_DECISION"
        }
        
        return prompt_to_action.get(state.current_prompt)
    
    def _get_longest_road_owner(self, state) -> Optional[str]:
        """Get owner of longest road achievement."""
        # This would require analyzing road networks
        # For now, return placeholder
        return None
    
    def _get_largest_army_owner(self, state) -> Optional[str]:
        """Get owner of largest army achievement."""
        # This would require counting knight cards played
        # For now, return placeholder
        return None