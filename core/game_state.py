"""
Game state extraction for LLM players.

This module provides utilities to extract and serialize the Catan game state
into a format that LLMs can understand and reason about.
"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from catanatron.models.enums import RESOURCES, DEVELOPMENT_CARDS, ActionType, ActionPrompt, SETTLEMENT, CITY, ROAD
from catanatron.models.player import Color
from catanatron.state_functions import (
    get_player_buildings,
    player_key,
    player_num_resource_cards,
    player_has_rolled,
)
from .axial_mapper import HexAxialMapper


class GameStateExtractor:
    """
    Extracts and formats Catan game state for LLM consumption.
    
    Converts the complex internal game state into a structured,
    human-readable format that provides all necessary information
    for strategic decision-making.
    """
    
    def __init__(self):
        self.hex_mapper = HexAxialMapper()
    
    def _make_json_serializable(self, obj):
        """Convert objects to JSON-serializable format."""
        if isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            # Convert objects with attributes to dictionaries
            return self._make_json_serializable(obj.__dict__)
        else:
            return obj
    
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
        
        # First extract tiles to register them with hex mapper
        tiles_info = self._extract_tiles_info(state.board)
        self.hex_mapper.register_tiles(tiles_info)
        
        # Map Catanatron's board structure to our coordinate system
        self.hex_mapper.map_catanatron_board(state.board)
        
        game_state = {
            "turn_number": getattr(state, 'num_turns', 0),
            "board_state": self._extract_board_state(state),
            "current_player": self._extract_player_state(state, current_player_color, detailed=True),
            "opponents": self._extract_opponents_state(state, current_player_color)
        }
        
        # Ensure everything is JSON serializable
        return self._make_json_serializable(game_state)
    
    def _get_player_attribute(self, state, color: Color, attribute: str, default=0):
        """
        Helper method to get a player-specific attribute from the flattened state.
        
        Args:
            state: Game state
            color: Player color
            attribute: Attribute name (e.g., 'VICTORY_POINTS', 'WOOD_IN_HAND')
            default: Default value if attribute not found
            
        Returns:
            Attribute value or default
        """
        player_prefix = player_key(state, color)
        full_key = f"{player_prefix}_{attribute}"
        return state.player_state.get(full_key, default)
    
    def _extract_game_info(self, state) -> Dict[str, Any]:
        """Extract basic game information."""
        return {
            "turn_number": getattr(state, 'num_turns', 0),
            "current_player_color": state.current_color().value,
            "winning_player": None,  # Will be determined by game engine
            "game_phase": "playing"  # Simplified for now
        }
    
    def _extract_board_state(self, state) -> Dict[str, Any]:
        """Extract board-related information."""
        board = state.board
        
        # Get tiles with axial coordinate information
        tiles_with_axial = []
        for coord, tile_info in self.hex_mapper.tiles.items():
            q, r = coord
            tile_dict = {
                'coordinate': coord,
                'axial_coord': f"({q},{r})",
                'resource': tile_info.resource,
                'number': tile_info.number,
                'name': tile_info.name,
                'neighbors': [self.hex_mapper.tiles[ncoord].name for ncoord in tile_info.neighbors if ncoord in self.hex_mapper.tiles],
                'has_robber': False  # Will be updated if robber is present
            }
            tiles_with_axial.append(tile_dict)
        
        return {
            "robber_position": self._get_robber_position(board),
            "ports": self._extract_ports_info(board),
            "tiles": tiles_with_axial,
            "intersections": self._extract_intersections_info(),
            "edges": self._extract_edges_info(),
            "longest_road_owner": self._get_longest_road_owner(state),
            "largest_army_owner": self._get_largest_army_owner(state)
        }
    
    def _extract_player_state(self, state, color: Color, detailed: bool = False) -> Dict[str, Any]:
        """Extract detailed state for a specific player."""
        if detailed:
            # Current player - show victory_points and detailed info
            base_info = {
                "color": color.value,
                "victory_points": self._get_player_attribute(state, color, "VICTORY_POINTS", 0),
                "resource_cards_count": player_num_resource_cards(state, color),
                "development_cards_count": sum(
                    self._get_player_attribute(state, color, f"{card}_IN_HAND", 0)
                    for card in DEVELOPMENT_CARDS
                ),
                "has_rolled_this_turn": player_has_rolled(state, color),
                "buildings": self._extract_buildings(state, color),
                "resources": {
                    resource: self._get_player_attribute(state, color, f"{resource}_IN_HAND", 0)
                    for resource in RESOURCES
                },
                "development_cards_in_hand": {
                    card: self._get_player_attribute(state, color, f"{card}_IN_HAND", 0)
                    for card in DEVELOPMENT_CARDS
                }
            }
        else:
            # Opponents - show public_victory_points and limited info
            base_info = {
                "color": color.value,
                "public_victory_points": self._get_player_attribute(state, color, "VICTORY_POINTS", 0),
                "resource_cards_count": player_num_resource_cards(state, color),
                "development_cards_count": sum(
                    self._get_player_attribute(state, color, f"{card}_IN_HAND", 0)
                    for card in DEVELOPMENT_CARDS
                ),
                "has_rolled_this_turn": player_has_rolled(state, color),
                "buildings": self._extract_buildings(state, color)
            }
        
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
    
    
    def _extract_buildings(self, state, color: Color) -> Dict[str, Any]:
        """Extract building information for a player."""
        settlements = list(get_player_buildings(state, color, SETTLEMENT))
        cities = list(get_player_buildings(state, color, CITY))
        roads = list(get_player_buildings(state, color, ROAD))
        
        return {
            "settlements": settlements,
            "cities": cities,
            "roads": roads,
            "settlements_available": 5 - len(settlements),
            "cities_available": 4 - len(cities),
            "roads_available": 15 - len(roads)
        }
    
    
    def _get_robber_position(self, board) -> Optional[Tuple[int, int, int]]:
        """Get current robber position."""
        return getattr(board, 'robber_coordinate', None)
    
    def _extract_ports_info(self, board) -> List[Dict[str, Any]]:
        """Extract information about ports on the board with spatial context."""
        ports = []
        
        # Known port locations with directions (hardcoded for BASE_MAP_TEMPLATE)
        port_directions = {
            "WOOD": "Southeast side", "BRICK": "Southwest side", "SHEEP": "Northwest side",
            "WHEAT": "East side", "ORE": "Northeast side"
        }
        generic_port_directions = ["West side", "Northwest side", "East side", "Southwest side"]
        
        # Extract port information from Catanatron board
        if hasattr(board, 'map') and hasattr(board.map, 'port_nodes'):
            generic_port_count = 0
            
            for port_resource, node_ids in board.map.port_nodes.items():
                # Convert sets to lists for JSON serialization
                if isinstance(node_ids, set):
                    node_ids = list(node_ids)
                
                # Handle generic ports (3:1 trade for all resources)
                if port_resource is None:
                    resource_desc = "Any"
                    trade_ratio = "3:1"
                    direction = generic_port_directions[generic_port_count % len(generic_port_directions)]
                    generic_port_count += 1
                else:
                    resource_desc = f"{port_resource}"
                    trade_ratio = "2:1"
                    direction = port_directions.get(port_resource, "Unknown side")
                
                ports.append({
                    "resource": resource_desc,
                    "trade_ratio": trade_ratio,
                    "direction": direction,
                    "node_ids": node_ids,
                    "description": f"{resource_desc} Port ({trade_ratio}) - {direction}"
                })
        
        return ports
    
    def _extract_tiles_info(self, board) -> List[Dict[str, Any]]:
        """Extract tile information."""
        tiles = []
        if hasattr(board, 'map') and hasattr(board.map, 'tiles'):
            for coordinate, tile in board.map.tiles.items():
                # Skip ports - only include actual resource tiles
                if not hasattr(tile, 'number'):
                    continue
                    
                tiles.append({
                    "coordinate": coordinate,
                    "resource": getattr(tile, 'resource', None),
                    "number": getattr(tile, 'number', None),
                    "has_robber": getattr(board, 'robber_coordinate', None) == coordinate
                })
        return tiles
    
    def _extract_intersections_info(self) -> List[Dict[str, Any]]:
        """Extract intersection information with adjacency."""
        intersections = []
        
        for int_id, int_info in self.hex_mapper.intersections.items():
            intersection_dict = {
                'id': int_id,
                'tiles': int_info.tile_names,
                'description': self.hex_mapper.get_intersection_description(int_id),
                'adjacent_intersections': int_info.adjacent_intersections,
                'connected_edges': int_info.connected_edges
            }
            intersections.append(intersection_dict)
        
        return intersections
    
    def _extract_edges_info(self) -> List[Dict[str, Any]]:
        """Extract edge information with adjacency."""
        edges = []
        
        for edge_id, edge_info in self.hex_mapper.edges.items():
            edge_dict = {
                'id': edge_id,
                'tiles': edge_info.tile_names,
                'description': self.hex_mapper.get_edge_description(edge_id),
                'intersections': edge_info.intersections,
                'name': edge_info.name
            }
            edges.append(edge_dict)
        
        return edges
    
    def _get_available_building_spots(self, state) -> Dict[str, List]:
        """Get available spots for building."""
        # This would require more detailed analysis of the board state
        # For now, return placeholder
        return {
            "settlement_spots": [],
            "city_upgrade_spots": [],
            "road_spots": []
        }
    
    
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