"""
Axial Coordinate + Adjacency System for Catan hexagonal board representation.

This system uses axial coordinates (q,r) with explicit adjacency information
to help LLMs understand the hexagonal board topology, tile positions, 
intersections, and road connections.
"""

from typing import Dict, Tuple, Optional, List, Any, Set
import math


class HexAxialMapper:
    """Axial coordinate system with adjacency for hexagonal Catan board."""
    
    def __init__(self):
        # Axial directions for hex grid navigation
        # Using cube coordinate directions converted to axial
        self.HEX_DIRECTIONS = [
            (1, 0),   # East
            (1, -1),  # Northeast  
            (0, -1),  # Northwest
            (-1, 0),  # West
            (-1, 1),  # Southwest
            (0, 1),   # Southeast
        ]
        
        # Direction names for readability
        self.DIRECTION_NAMES = [
            "E", "NE", "NW", "W", "SW", "SE"
        ]
        
        # Store tile information with adjacency
        self.tiles = {}  # (q,r) -> TileInfo
        self.tile_name_to_coord = {}  # name -> (q,r)
        
        # Store intersection and edge information
        self.intersections = {}  # intersection_id -> IntersectionInfo
        self.edges = {}  # edge_id -> EdgeInfo
        
        # Action mappings for LLM communication
        self.action_mappings = {}  # action_index -> readable_description
    
    def _get_direction_name(self, coord: Tuple[int, int, int]) -> str:
        """Get direction name for a coordinate, with fallback for unknown coordinates."""
        if coord in self.coordinate_to_direction:
            return self.coordinate_to_direction[coord]
        
        # Fallback: generate name based on coordinate values
        x, y, z = coord
        if abs(x) > abs(y) and abs(x) > abs(z):
            base = "East" if x > 0 else "West"
        elif abs(y) > abs(z):
            base = "Northwest" if y > 0 else "Southeast" 
        else:
            base = "Northeast" if z < 0 else "Southwest"
            
        # Add distance if far from center
        distance = max(abs(x), abs(y), abs(z))
        if distance > 2:
            return f"Far{base}{distance}"
        elif distance == 2:
            return f"Far{base}"
        else:
            return base
    
    def register_tiles(self, tiles: List[Dict[str, Any]]):
        """Register tile information for creating unique names."""
        self.coordinate_to_tile_info.clear()
        self.tile_name_to_coordinate.clear()
        
        # Debug: print tiles to see what we're working with
        print(f"Registering {len(tiles)} tiles:")
        for i, tile in enumerate(tiles[:3]):  # Show first 3
            print(f"  Tile {i}: {tile}")
        
        # Count occurrences of each resource-number combination
        resource_number_counts = {}
        
        for tile in tiles:
            try:
                coord = tuple(tile['coordinate']) if isinstance(tile['coordinate'], list) else tile['coordinate']
                resource = tile.get('resource')
                number = tile.get('number')
                
                # Handle desert tiles (resource is None)
                if not resource:
                    resource = "Desert"
                    number = None
                
                # Count this resource-number combination
                key = (resource, number)
                resource_number_counts[key] = resource_number_counts.get(key, 0) + 1
                print(f"  Counted tile: {coord} -> {resource}-{number} (total: {resource_number_counts[key]})")
                
            except Exception as e:
                print(f"Error processing tile {tile}: {e}")
                continue
        
        # Create unique names
        resource_number_counters = {}
        
        for tile in tiles:
            try:
                coord = tuple(tile['coordinate']) if isinstance(tile['coordinate'], list) else tile['coordinate']
                resource = tile.get('resource')
                number = tile.get('number')
                direction = self._get_direction_name(coord)
                
                # Handle desert tiles (resource is None)
                if not resource:
                    resource = "Desert"
                    number = None
                
                # Create base name
                if resource == "Desert":
                    base_name = f"{direction}-Desert"
                elif number:
                    base_name = f"{direction}-{resource}-{number}"
                else:
                    base_name = f"{direction}-{resource}"
                
                # Handle duplicates by checking if this resource-number combo appears multiple times
                resource_number_key = (resource, number)
                count = resource_number_counts.get(resource_number_key, 0)
                print(f"  Creating name for {coord}: {resource_number_key} (count: {count})")
                
                if count > 1:
                    # Multiple tiles with same resource-number, keep direction-based unique name
                    unique_name = base_name
                else:
                    # Single tile with this resource-number, can use shorter name
                    if resource == "Desert":
                        unique_name = "Desert"
                    elif number:
                        unique_name = f"{resource}-{number}"
                    else:
                        unique_name = resource
                
                # Ensure uniqueness by checking if name already exists
                counter = 1
                original_unique_name = unique_name
                while unique_name in self.tile_name_to_coordinate:
                    unique_name = f"{original_unique_name}-{counter}"
                    counter += 1
                
                self.coordinate_to_tile_info[coord] = (resource, number, unique_name)
                self.tile_name_to_coordinate[unique_name] = coord
                print(f"  Final name: {unique_name}")
                
            except Exception as e:
                print(f"Error creating name for tile {tile}: {e}")
                continue
    
    def get_tile_name(self, coord: Tuple[int, int, int]) -> str:
        """Get human-readable name for a tile coordinate."""
        if coord in self.coordinate_to_tile_info:
            return self.coordinate_to_tile_info[coord][2]  # unique_name
        
        # Fallback for unknown coordinates
        direction = self._get_direction_name(coord)
        return f"{direction}-Unknown"
    
    def get_coordinate_from_name(self, name: str) -> Optional[Tuple[int, int, int]]:
        """Get coordinate from tile name."""
        return self.tile_name_to_coordinate.get(name)
    
    def create_road_name(self, coord1: Tuple[int, int, int], coord2: Tuple[int, int, int]) -> str:
        """Create a road name between two tile coordinates."""
        tile1_name = self.get_tile_name(coord1)
        tile2_name = self.get_tile_name(coord2)
        
        # Sort names for consistency
        if tile1_name <= tile2_name:
            return f"{tile1_name}--{tile2_name}"
        else:
            return f"{tile2_name}--{tile1_name}"
    
    def register_action_mapping(self, action_index: int, action_description: str, readable_description: str):
        """Register mapping between action indices and human-readable descriptions."""
        self.action_index_to_description[action_index] = readable_description
        self.description_to_action_index[readable_description] = action_index
    
    def get_action_index_from_description(self, description: str) -> Optional[int]:
        """Get action index from human-readable description."""
        return self.description_to_action_index.get(description)
    
    def get_readable_description(self, action_index: int) -> Optional[str]:
        """Get human-readable description from action index."""
        return self.action_index_to_description.get(action_index)
    
    def clear_action_mappings(self):
        """Clear action mappings (useful between turns)."""
        self.action_index_to_description.clear()
        self.description_to_action_index.clear()