"""
Action parsing and description for LLM players.

This module provides utilities to convert Catanatron actions into
human-readable descriptions and parse LLM responses back into actions.
"""

from typing import Dict, List, Any, Optional, Tuple
from catanatron.models.enums import Action, ActionType, RESOURCES, DEVELOPMENT_CARDS
from .axial_mapper import HexAxialMapper


class ActionParser:
    """
    Handles conversion between Catanatron actions and human-readable descriptions.
    
    This class helps LLMs understand what actions are available and converts
    their responses back into valid Catanatron Action objects.
    """
    
    def __init__(self, hex_mapper: Optional[HexAxialMapper] = None):
        """Initialize the action parser with description templates."""
        self.hex_mapper = hex_mapper or HexAxialMapper()
        self.action_descriptions = {
            ActionType.ROLL: "Roll the dice to start your turn",
            ActionType.END_TURN: "End your current turn",
            ActionType.BUILD_SETTLEMENT: "Build a settlement at position {position}",
            ActionType.BUILD_CITY: "Upgrade settlement to city at position {position}",
            ActionType.BUILD_ROAD: "Build a road at position {position}",
            ActionType.BUY_DEVELOPMENT_CARD: "Buy a development card",
            ActionType.PLAY_KNIGHT_CARD: "Play a Knight development card",
            ActionType.PLAY_YEAR_OF_PLENTY: "Play Year of Plenty card to gain {resources}",
            ActionType.PLAY_MONOPOLY: "Play Monopoly card to collect all {resource}",
            ActionType.PLAY_ROAD_BUILDING: "Play Road Building card to build 2 roads",
            ActionType.MARITIME_TRADE: "Trade {offered} for {requested} at {ratio} rate",
            ActionType.OFFER_TRADE: "Offer trade: give {offered} for {requested}",
            ActionType.ACCEPT_TRADE: "Accept the proposed trade",
            ActionType.REJECT_TRADE: "Reject the proposed trade",
            ActionType.MOVE_ROBBER: "Move robber to {position} and steal from {target}",
            ActionType.DISCARD: "Discard {resources} (required due to 7 rolled)"
        }
    
    def describe_actions(self, actions: List[Action]) -> Dict[int, str]:
        """
        Convert a list of actions to human-readable descriptions.
        
        Args:
            actions: List of Catanatron Action objects
            
        Returns:
            Dictionary mapping action indices to descriptions
        """
        descriptions = {}
        self.hex_mapper.clear_action_mappings()
        
        for i, action in enumerate(actions):
            # Create human-readable description using hex mapper
            readable_description = self._create_axial_description(action, i)
            descriptions[i] = readable_description
            
            # Register mapping for LLM lookup
            self.hex_mapper.register_action_mapping(i, readable_description)
            
        return descriptions
    
    def get_readable_action_descriptions(self, actions: List[Action]) -> Dict[int, str]:
        """Get readable action descriptions for display to LLM."""
        readable_descriptions = {}
        
        for i, action in enumerate(actions):
            readable_desc = self.hex_mapper.get_action_description(i)
            if readable_desc:
                readable_descriptions[i] = readable_desc
            else:
                readable_descriptions[i] = self._create_axial_description(action, i)
                
        return readable_descriptions
    
    def _describe_single_action(self, action: Action) -> str:
        """
        Create a human-readable description for a single action.
        
        Args:
            action: Catanatron Action object
            
        Returns:
            Human-readable description string
        """
        action_type = action.action_type
        value = action.value
        
        if action_type not in self.action_descriptions:
            return f"Unknown action: {action_type}"
        
        template = self.action_descriptions[action_type]
        
        # Handle actions that don't need parameter substitution
        if "{" not in template:
            return template
        
        # Handle specific action types with parameter substitution
        try:
            return self._format_action_description(action_type, template, value)
        except Exception:
            return f"{action_type.value}: {value}"
    
    def _create_axial_description(self, action: Action, action_index: int) -> str:
        """Create human-readable description using axial coordinate system."""
        action_type = action.action_type
        value = action.value
        
        try:
            if action_type == ActionType.BUILD_SETTLEMENT:
                # Map action index to intersection description
                intersection_desc = self._get_intersection_for_action(action_index)
                if intersection_desc:
                    return f"Build settlement at {intersection_desc}"
                else:
                    return f"Build settlement at intersection {action_index} (node {value})"
            
            elif action_type == ActionType.BUILD_ROAD:
                # Map action index to edge description
                edge_desc = self._get_edge_for_action(action_index)
                if edge_desc:
                    return f"Build road: {edge_desc}"
                else:
                    return f"Build road at edge {action_index} (edge {value})"
            
            elif action_type == ActionType.BUILD_CITY:
                # Map action index to intersection description  
                intersection_desc = self._get_intersection_for_action(action_index)
                if intersection_desc:
                    return f"Upgrade to city at {intersection_desc}"
                else:
                    return f"Upgrade to city at intersection {action_index} (node {value})"
            
            elif action_type == ActionType.MOVE_ROBBER:
                # Handle robber movement with tile coordinate
                if isinstance(value, (list, tuple)) and len(value) >= 3:
                    cube_coord = tuple(value[:3])
                    axial_coord = self.hex_mapper.cube_to_axial(cube_coord)
                    if axial_coord in self.hex_mapper.tiles:
                        tile_name = self.hex_mapper.tiles[axial_coord].name
                        return f"Move robber to {tile_name}"
                    else:
                        return f"Move robber to coordinate {axial_coord}"
                else:
                    return f"Move robber (action {action_index})"
            
            else:
                # For other actions, use basic description
                if action_type == ActionType.ROLL:
                    return "Roll dice to start turn"
                elif action_type == ActionType.END_TURN:
                    return "End turn"
                elif action_type == ActionType.BUY_DEVELOPMENT_CARD:
                    return "Buy development card"
                else:
                    return f"{action_type.name.replace('_', ' ').title()}"
                
        except Exception as e:
            # Fallback description
            return f"Action {action_index}: {action_type.name}"
    
    def _get_intersection_for_action(self, action_index: int) -> Optional[str]:
        """Get intersection description for settlement/city action index."""
        # Direct mapping: action index to intersection ID (assuming action_index = node_id)
        intersection_id = f"I{action_index}"
        
        # If we have this intersection, return its description
        if intersection_id in self.hex_mapper.intersections:
            return self.hex_mapper.get_intersection_description(intersection_id)
        
        # Check if this action corresponds to a port intersection
        if intersection_id in self.hex_mapper.port_intersections:
            port_info = self.hex_mapper.port_intersections[intersection_id]
            port_str = ", ".join(port_info)
            return f"{intersection_id}: Port settlement spot - Provides access to {port_str}"
        
        # For intersections we haven't mapped yet, show a descriptive fallback
        return f"{intersection_id}: Settlement spot (node {action_index})"
    
    def _get_edge_for_action(self, action_index: int) -> Optional[str]:
        """Get edge description for road action index."""
        # Simple mapping: action index to edge index
        # This assumes that road actions are ordered by edge
        if action_index < len(self.hex_mapper.edges):
            edge_ids = list(self.hex_mapper.edges.keys())
            if action_index < len(edge_ids):
                edge_id = edge_ids[action_index]
                return self.hex_mapper.get_edge_description(edge_id)
        return None
    
    def _format_action_description(self, action_type: ActionType, template: str, value: Any) -> str:
        """
        Format action description template with specific parameters.
        
        Args:
            action_type: Type of action
            template: Description template string
            value: Action value/parameters
            
        Returns:
            Formatted description string
        """
        if action_type in [ActionType.BUILD_SETTLEMENT, ActionType.BUILD_CITY, ActionType.BUILD_ROAD]:
            return template.format(position=self._format_position(value))
            
        elif action_type == ActionType.PLAY_YEAR_OF_PLENTY:
            if isinstance(value, tuple) and len(value) == 2:
                resources = f"{value[0]} and {value[1]}"
                return template.format(resources=resources)
            return template.format(resources=str(value))
            
        elif action_type == ActionType.PLAY_MONOPOLY:
            return template.format(resource=value)
            
        elif action_type == ActionType.MARITIME_TRADE:
            return self._format_maritime_trade(value)
            
        elif action_type in [ActionType.OFFER_TRADE, ActionType.ACCEPT_TRADE]:
            return self._format_player_trade(action_type, value)
            
        elif action_type == ActionType.MOVE_ROBBER:
            return self._format_robber_move(value)
            
        elif action_type == ActionType.DISCARD:
            return template.format(resources=self._format_resource_list(value))
            
        else:
            # Fallback for unknown parameter formats
            return template.format(value=value)
    
    def _format_position(self, position: Any) -> str:
        """Format position information for building actions."""
        if isinstance(position, tuple):
            return f"coordinate {position}"
        elif isinstance(position, (int, str)):
            return f"#{position}"
        else:
            return str(position)
    
    def _format_maritime_trade(self, value: Any) -> str:
        """Format maritime trade description."""
        if isinstance(value, tuple) and len(value) >= 5:
            # Maritime trade format: (wood_give, brick_give, sheep_give, wheat_give, ore_give, resource_wanted)
            offered_resources = []
            for i, resource in enumerate(RESOURCES):
                if i < len(value) - 1 and value[i] > 0:
                    offered_resources.append(f"{value[i]} {resource}")
            
            wanted_resource = value[-1] if len(value) > 5 else "unknown"
            offered_str = ", ".join(offered_resources) if offered_resources else "resources"
            
            # Determine trade ratio
            total_offered = sum(value[:-1]) if len(value) > 1 else 0
            ratio = f"{total_offered}:1" if total_offered > 0 else "port"
            
            return f"Trade {offered_str} for 1 {wanted_resource} at {ratio} rate"
        
        return f"Maritime trade: {value}"
    
    def _format_player_trade(self, action_type: ActionType, value: Any) -> str:
        """Format player-to-player trade description."""
        if isinstance(value, tuple) and len(value) >= 10:
            # Trade format: first 5 elements are offered, last 5 are requested
            offered = self._format_resource_freqdeck(value[:5])
            requested = self._format_resource_freqdeck(value[5:10])
            
            if action_type == ActionType.OFFER_TRADE:
                return f"Offer trade: give {offered} for {requested}"
            else:
                return f"Accept trade: give {offered} for {requested}"
        
        return f"{action_type.value}: {value}"
    
    def _format_robber_move(self, value: Any) -> str:
        """Format robber movement description."""
        if isinstance(value, tuple) and len(value) >= 2:
            position, target = value[0], value[1]
            position_str = self._format_position(position)
            
            if target is None:
                return f"Move robber to {position_str} (no one to steal from)"
            else:
                return f"Move robber to {position_str} and steal from {target}"
        
        return f"Move robber: {value}"
    
    def _format_resource_list(self, resources: Any) -> str:
        """Format a list of resources for discard actions."""
        if isinstance(resources, list):
            if not resources:
                return "no resources"
            return ", ".join(str(r) for r in resources)
        elif isinstance(resources, dict):
            resource_strs = []
            for resource, count in resources.items():
                if count > 0:
                    resource_strs.append(f"{count} {resource}")
            return ", ".join(resource_strs) if resource_strs else "no resources"
        else:
            return str(resources)
    
    def _format_resource_freqdeck(self, freqdeck: tuple) -> str:
        """Format a resource frequency deck (5-tuple) into readable string."""
        if len(freqdeck) != 5:
            return str(freqdeck)
        
        resources = []
        for i, resource in enumerate(RESOURCES):
            count = freqdeck[i]
            if count > 0:
                resources.append(f"{count} {resource}")
        
        return ", ".join(resources) if resources else "nothing"
    
    def get_action_categories(self, actions: List[Action]) -> Dict[str, List[int]]:
        """
        Categorize actions by type for better LLM understanding.
        
        Args:
            actions: List of available actions
            
        Returns:
            Dictionary mapping categories to action indices
        """
        categories = {
            "building": [],
            "trading": [],
            "development_cards": [],
            "game_flow": [],
            "special": []
        }
        
        building_actions = {
            ActionType.BUILD_SETTLEMENT, ActionType.BUILD_CITY, ActionType.BUILD_ROAD
        }
        trading_actions = {
            ActionType.MARITIME_TRADE, ActionType.OFFER_TRADE, 
            ActionType.ACCEPT_TRADE, ActionType.REJECT_TRADE
        }
        dev_card_actions = {
            ActionType.BUY_DEVELOPMENT_CARD, ActionType.PLAY_KNIGHT_CARD,
            ActionType.PLAY_YEAR_OF_PLENTY, ActionType.PLAY_MONOPOLY,
            ActionType.PLAY_ROAD_BUILDING
        }
        game_flow_actions = {
            ActionType.ROLL, ActionType.END_TURN
        }
        
        for i, action in enumerate(actions):
            action_type = action.action_type
            
            if action_type in building_actions:
                categories["building"].append(i)
            elif action_type in trading_actions:
                categories["trading"].append(i)
            elif action_type in dev_card_actions:
                categories["development_cards"].append(i)
            elif action_type in game_flow_actions:
                categories["game_flow"].append(i)
            else:
                categories["special"].append(i)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}
    
    def get_strategic_advice(self, actions: List[Action], game_phase: str) -> List[str]:
        """
        Provide strategic advice based on available actions and game phase.
        
        Args:
            actions: List of available actions
            game_phase: Current phase of the game (early/mid/late)
            
        Returns:
            List of strategic advice strings
        """
        advice = []
        action_types = {action.action_type for action in actions}
        
        if game_phase == "early":
            if ActionType.BUILD_SETTLEMENT in action_types:
                advice.append("Early game: Focus on expanding with settlements to secure resources")
            if ActionType.BUILD_ROAD in action_types:
                advice.append("Build roads to secure good settlement spots before opponents")
                
        elif game_phase == "mid":
            if ActionType.BUILD_CITY in action_types:
                advice.append("Mid game: Upgrade settlements to cities for double resource production")
            if ActionType.BUY_DEVELOPMENT_CARD in action_types:
                advice.append("Consider development cards for victory points and strategic advantages")
                
        elif game_phase == "late":
            if ActionType.BUY_DEVELOPMENT_CARD in action_types:
                advice.append("Late game: Development cards may provide the final victory points needed")
            advice.append("Focus on actions that directly lead to victory points")
        
        # Trading advice
        if any(t in action_types for t in [ActionType.MARITIME_TRADE, ActionType.OFFER_TRADE]):
            advice.append("Consider trading to get resources needed for high-value buildings")
        
        return advice