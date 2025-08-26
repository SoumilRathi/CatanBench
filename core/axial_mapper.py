"""
Axial Coordinate + Adjacency System for Catan hexagonal board representation.

This system uses axial coordinates (q,r) with explicit adjacency information
to help LLMs understand the hexagonal board topology, tile positions, 
intersections, and road connections.
"""

from typing import Dict, Tuple, Optional, List, Any
from dataclasses import dataclass


@dataclass
class TileInfo:
    """Information about a tile on the hex board."""
    coord: Tuple[int, int]  # (q, r) axial coordinates
    resource: Optional[str]
    number: Optional[int]
    name: str  # Human readable name
    neighbors: List[Tuple[int, int]]  # Adjacent tile coordinates
    intersections: List[str]  # Intersection IDs around this tile
    edges: List[str]  # Edge IDs around this tile


@dataclass  
class IntersectionInfo:
    """Information about an intersection (settlement/city spot)."""
    id: str  # Unique identifier
    tiles: List[Tuple[int, int]]  # 2-3 tiles that meet at this intersection
    tile_names: List[str]  # Human readable tile names
    adjacent_intersections: List[str]  # Connected intersection IDs
    connected_edges: List[str]  # Edge IDs connected to this intersection


@dataclass
class EdgeInfo:
    """Information about an edge (road spot).""" 
    id: str  # Unique identifier
    tiles: List[Tuple[int, int]]  # 2 tiles this edge borders
    tile_names: List[str]  # Human readable tile names
    intersections: List[str]  # 2 intersection IDs this edge connects
    name: str  # Human readable name


@dataclass
class PortInfo:
    """Information about a port."""
    id: str  # Unique identifier
    resource: Optional[str]  # Resource type (None for 3:1 ports)
    trade_ratio: str  # "2:1", "3:1"
    direction: str  # Direction name (West, Northwest, etc.)
    coordinate: Tuple[int, int]  # Axial coordinate of port
    intersections: List[str]  # Intersection IDs connected to this port
    adjacent_tiles: List[str]  # Names of tiles adjacent to this port


class HexAxialMapper:
    """Axial coordinate system with adjacency for hexagonal Catan board."""
    
    def __init__(self):
        # Axial directions for hex grid navigation (clockwise from East)
        self.HEX_DIRECTIONS = [
            (1, 0),   # East (0)
            (0, 1),   # Southeast (1) 
            (-1, 1),  # Southwest (2)
            (-1, 0),  # West (3)
            (0, -1),  # Northwest (4)
            (1, -1),  # Northeast (5)
        ]
        
        # Direction names
        self.DIRECTION_NAMES = ["E", "SE", "SW", "W", "NW", "NE"]
        
        # Port intersections will be determined from actual Catanatron board data
        # rather than hardcoded positions
        self.port_intersections: Dict[str, List[str]] = {}  # intersection_id -> [port descriptions]
        
        # Store all board information
        self.tiles: Dict[Tuple[int, int], TileInfo] = {}
        self.intersections: Dict[str, IntersectionInfo] = {}
        self.edges: Dict[str, EdgeInfo] = {}
        self.ports: Dict[str, PortInfo] = {}
        
        # Lookup mappings
        self.tile_name_to_coord: Dict[str, Tuple[int, int]] = {}
        self.action_mappings: Dict[int, str] = {}
        
        # Node ID to intersection mapping (for Catanatron integration)
        self.node_to_intersection: Dict[int, str] = {}
        self.edge_to_edge_info: Dict[Tuple[int, int], str] = {}
        
        # Port coordinate to intersection mapping
        self.port_intersections: Dict[Tuple[int, int], List[str]] = {}
    
    def cube_to_axial(self, cube_coord: Tuple[int, int, int]) -> Tuple[int, int]:
        """Convert cube coordinates (x,y,z) to axial coordinates (q,r)."""
        x, y, z = cube_coord
        q = x
        r = z
        return (q, r)
    
    def axial_to_cube(self, axial_coord: Tuple[int, int]) -> Tuple[int, int, int]:
        """Convert axial coordinates (q,r) to cube coordinates (x,y,z)."""
        q, r = axial_coord
        x = q
        z = r
        return (x, -x - z, z)
    
    def get_neighbors(self, coord: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all 6 neighboring coordinates in axial system."""
        q, r = coord
        neighbors = []
        for dq, dr in self.HEX_DIRECTIONS:
            neighbors.append((q + dq, r + dr))
        return neighbors
    
    def get_distance(self, coord1: Tuple[int, int], coord2: Tuple[int, int]) -> int:
        """Get hex distance between two coordinates."""
        x1, y1, z1 = self.axial_to_cube(coord1)
        x2, y2, z2 = self.axial_to_cube(coord2)
        return max(abs(x1 - x2), abs(y1 - y2), abs(z1 - z2))
    
    def create_tile_name(self, coord: Tuple[int, int], resource: str, number: Optional[int]) -> str:
        """Create a readable name for a tile."""
        q, r = coord
        
        # Handle center tile
        if coord == (0, 0):
            if resource == "Desert" or not resource:
                return "CENTER-Desert"
            return f"CENTER-{resource}{number if number else ''}"
        
        # Create position description based on coordinate
        distance = max(abs(q), abs(r), abs(-q-r))
        
        if distance == 1:
            # Inner ring - use simple directions
            if coord == (1, 0): direction = "E"
            elif coord == (0, 1): direction = "SE"  
            elif coord == (-1, 1): direction = "SW"
            elif coord == (-1, 0): direction = "W"
            elif coord == (0, -1): direction = "NW"
            elif coord == (1, -1): direction = "NE"
            else: direction = f"({q},{r})"
        else:
            # Outer ring - use coordinate notation
            direction = f"({q},{r})"
        
        # Create final name
        if resource == "Desert" or not resource:
            return f"{direction}-Desert"
        elif number:
            return f"{direction}-{resource}{number}"
        else:
            return f"{direction}-{resource}"
    
    def register_tiles(self, tiles_data: List[Dict[str, Any]]):
        """Register all tiles and build adjacency information."""
        self.tiles.clear()
        self.tile_name_to_coord.clear()
        
        # First pass: create all tiles
        for tile_data in tiles_data:
            try:
                # Convert cube coordinates to axial
                cube_coord = tuple(tile_data['coordinate'])
                axial_coord = self.cube_to_axial(cube_coord)
                
                resource = tile_data.get('resource', 'Desert')
                number = tile_data.get('number')
                
                # Handle None resource (desert)
                if not resource:
                    resource = "Desert"
                
                # Create tile name
                tile_name = self.create_tile_name(axial_coord, resource, number)
                
                # Get neighbors
                neighbors = self.get_neighbors(axial_coord)
                
                # Create tile info (intersections and edges will be added later)
                tile_info = TileInfo(
                    coord=axial_coord,
                    resource=resource,
                    number=number,
                    name=tile_name,
                    neighbors=neighbors,
                    intersections=[],
                    edges=[]
                )
                
                self.tiles[axial_coord] = tile_info
                self.tile_name_to_coord[tile_name] = axial_coord
                
            except Exception as e:
                print(f"Error processing tile {tile_data}: {e}")
                continue
        
        # Second pass: generate intersections and edges
        self._generate_intersections()
        self._generate_edges()
        
        # Third pass: identify port-adjacent intersections
        self._identify_port_intersections()
    
    def map_catanatron_board(self, catanatron_board):
        """Map Catanatron's internal board structure to our coordinate system."""
        # Extract and register port information
        self._register_ports_from_catanatron(catanatron_board)
        
        # Map actual port nodes to intersections
        self._map_port_nodes_to_intersections(catanatron_board)
    
    def _register_ports_from_catanatron(self, catanatron_board):
        """Extract port information from Catanatron board."""
        if not hasattr(catanatron_board, 'map') or not hasattr(catanatron_board.map, 'ports_by_id'):
            return
        
        port_id = 0
        direction_names = {
            0: "West", 1: "Northwest", 2: "Northeast", 
            3: "East", 4: "Southeast", 5: "Southwest"
        }
        
        for port in catanatron_board.map.ports_by_id.values():
            # Get port resource and trade ratio
            resource = getattr(port, 'resource', None)
            trade_ratio = "2:1" if resource else "3:1"
            resource_name = resource if resource else "Any"
            
            # Get port direction
            direction = getattr(port, 'direction', None)
            direction_name = direction_names.get(direction, "Unknown") if direction is not None else "Unknown"
            
            # Create port info
            port_key = f"P{port_id}"
            
            # For now, we'll map ports approximately - this could be refined
            # based on the actual port coordinate system
            port_info = PortInfo(
                id=port_key,
                resource=resource_name,
                trade_ratio=trade_ratio,
                direction=direction_name,
                coordinate=(0, 0),  # Placeholder - would need actual port coordinates
                intersections=[],  # Will be populated when we identify port intersections
                adjacent_tiles=[]
            )
            
            self.ports[port_key] = port_info
            port_id += 1
    
    def _generate_intersections(self):
        """Generate all intersections including edge intersections for complete Catan board."""
        self.intersections.clear()
        intersection_id = 0
        generated_intersections = set()  # Track unique intersections by their tile coordinates
        
        # First pass: Generate intersections from tile corners (2-3 tiles meeting)
        for coord, tile in self.tiles.items():
            q, r = coord
            
            # Each hex has 6 corners, we'll identify them by the tiles they connect
            # Corner directions (which neighbors each corner connects to)
            corner_directions = [
                [0, 5],  # E-NE corner
                [0, 1],  # E-SE corner  
                [1, 2],  # SE-SW corner
                [2, 3],  # SW-W corner
                [3, 4],  # W-NW corner
                [4, 5],  # NW-NE corner
            ]
            
            for corner_idx, directions in enumerate(corner_directions):
                # Get the tiles that meet at this corner
                corner_tiles = [coord]
                corner_tile_names = [tile.name]
                
                for dir_idx in directions:
                    neighbor_coord = (
                        q + self.HEX_DIRECTIONS[dir_idx][0],
                        r + self.HEX_DIRECTIONS[dir_idx][1]
                    )
                    if neighbor_coord in self.tiles:
                        corner_tiles.append(neighbor_coord)
                        corner_tile_names.append(self.tiles[neighbor_coord].name)
                
                # Create intersection if we have any tiles (including single tile edge cases)
                if len(corner_tiles) >= 1:
                    # Create unique identifier based on sorted tile coordinates
                    corner_tiles_sorted = tuple(sorted(corner_tiles))
                    
                    # Check if we already generated this intersection
                    if corner_tiles_sorted not in generated_intersections:
                        generated_intersections.add(corner_tiles_sorted)
                        
                        intersection_key = f"I{intersection_id}"
                        
                        # Create new intersection
                        intersection_info = IntersectionInfo(
                            id=intersection_key,
                            tiles=corner_tiles,
                            tile_names=corner_tile_names,
                            adjacent_intersections=[],  # Will be filled later
                            connected_edges=[]  # Will be filled later
                        )
                        
                        self.intersections[intersection_key] = intersection_info
                        
                        # Add this intersection to all tiles that touch it
                        for tile_coord in corner_tiles:
                            if tile_coord in self.tiles:
                                self.tiles[tile_coord].intersections.append(intersection_key)
                        
                        intersection_id += 1
        
        # Second pass: Generate edge intersections for outer ring tiles
        # These are intersections that appear at the edges of the board where only 1 tile exists
        # but there should still be valid settlement spots (often near ports)
        
        outer_ring_distance = 2  # Tiles in the outer ring
        
        for coord, tile in self.tiles.items():
            q, r = coord
            distance_from_center = max(abs(q), abs(r), abs(-q-r))
            
            # For outer ring tiles, check if we need additional edge intersections
            if distance_from_center == outer_ring_distance:
                # Check each corner direction to see if we're missing edge intersections
                for corner_idx in range(6):
                    # Calculate the position where an edge intersection might be
                    direction1_idx = corner_idx
                    direction2_idx = (corner_idx + 1) % 6
                    
                    neighbor1_coord = (
                        q + self.HEX_DIRECTIONS[direction1_idx][0],
                        r + self.HEX_DIRECTIONS[direction1_idx][1]
                    )
                    neighbor2_coord = (
                        q + self.HEX_DIRECTIONS[direction2_idx][0],
                        r + self.HEX_DIRECTIONS[direction2_idx][1]
                    )
                    
                    # If neither neighbor exists, this is likely an edge intersection spot
                    if (neighbor1_coord not in self.tiles and neighbor2_coord not in self.tiles):
                        # Create an edge intersection with just this tile
                        edge_tiles = [coord]
                        edge_tile_names = [tile.name]
                        edge_tiles_sorted = tuple(sorted(edge_tiles))
                        
                        # Only add if we haven't already created this intersection
                        if edge_tiles_sorted not in generated_intersections:
                            generated_intersections.add(edge_tiles_sorted)
                            
                            intersection_key = f"I{intersection_id}"
                            
                            # Create intersection with port designation
                            intersection_info = IntersectionInfo(
                                id=intersection_key,
                                tiles=edge_tiles,
                                tile_names=edge_tile_names + ["(Port Edge)"],  # Indicate it's near a port
                                adjacent_intersections=[],
                                connected_edges=[]
                            )
                            
                            self.intersections[intersection_key] = intersection_info
                            self.tiles[coord].intersections.append(intersection_key)
                            
                            intersection_id += 1
        
    
    def _generate_edges(self):
        """Generate all edges between adjacent tiles."""
        self.edges.clear()
        edge_id = 0
        processed_edges = set()
        
        # For each tile, create edges to its neighbors
        for coord, tile in self.tiles.items():
            for neighbor_coord in tile.neighbors:
                if neighbor_coord in self.tiles:
                    # Create edge between this tile and neighbor
                    edge_key = tuple(sorted([coord, neighbor_coord]))
                    
                    if edge_key not in processed_edges:
                        processed_edges.add(edge_key)
                        
                        tile1_coord, tile2_coord = edge_key
                        tile1_name = self.tiles[tile1_coord].name
                        tile2_name = self.tiles[tile2_coord].name
                        
                        edge_id_str = f"E{edge_id}"
                        edge_name = f"{tile1_name}--{tile2_name}"
                        
                        # Find intersections that this edge connects
                        # (intersections that involve both tiles)
                        connecting_intersections = []
                        for int_id, int_info in self.intersections.items():
                            if tile1_coord in int_info.tiles and tile2_coord in int_info.tiles:
                                connecting_intersections.append(int_id)
                        
                        edge_info = EdgeInfo(
                            id=edge_id_str,
                            tiles=[tile1_coord, tile2_coord],
                            tile_names=[tile1_name, tile2_name],
                            intersections=connecting_intersections,
                            name=edge_name
                        )
                        
                        self.edges[edge_id_str] = edge_info
                        
                        # Add this edge to both tiles
                        self.tiles[tile1_coord].edges.append(edge_id_str)
                        self.tiles[tile2_coord].edges.append(edge_id_str)
                        
                        # Add this edge to connecting intersections
                        for int_id in connecting_intersections:
                            self.intersections[int_id].connected_edges.append(edge_id_str)
                        
                        edge_id += 1
    
    def _map_port_nodes_to_intersections(self, catanatron_board):
        """Map actual Catanatron port nodes to intersections."""
        if not hasattr(catanatron_board, 'map') or not hasattr(catanatron_board.map, 'port_nodes'):
            return
        
        # Clear existing port information
        self.port_intersections.clear()
        
        # Map port nodes to intersections
        port_nodes = catanatron_board.map.port_nodes
        
        for port_resource, node_ids in port_nodes.items():
            if isinstance(node_ids, set):
                node_ids = list(node_ids)
            
            # Determine port info
            if port_resource is None:
                port_desc = "Any Port (3:1)"
            else:
                port_desc = f"{port_resource} Port (2:1)"
            
            # Map each node ID to intersection ID
            # Assumption: action index = node ID = intersection index
            for node_id in node_ids:
                intersection_id = f"I{node_id}"
                if intersection_id not in self.port_intersections:
                    self.port_intersections[intersection_id] = []
                self.port_intersections[intersection_id].append(port_desc)
    
    def _identify_port_intersections(self):
        """Legacy method - replaced by _map_port_nodes_to_intersections."""
        pass
    
    
    def get_intersection_description(self, intersection_id: str) -> str:
        """Get human-readable description of an intersection."""
        if intersection_id not in self.intersections:
            return f"Unknown intersection {intersection_id}"
        
        int_info = self.intersections[intersection_id]
        tile_names = int_info.tile_names
        
        # Filter out port edge markers and bracket info
        actual_tiles = [name for name in tile_names if not (name.startswith("[") or "(Port Edge)" in name)]
        
        # Build base description
        if len(actual_tiles) == 3:
            base_desc = f"{intersection_id}: Corner of {actual_tiles[0]}, {actual_tiles[1]}, {actual_tiles[2]}"
        elif len(actual_tiles) == 2:
            base_desc = f"{intersection_id}: Edge corner of {actual_tiles[0]} and {actual_tiles[1]}"
        elif len(actual_tiles) == 1:
            base_desc = f"{intersection_id}: Edge of {actual_tiles[0]}"
        else:
            base_desc = f"{intersection_id}: {'/'.join(actual_tiles)}"
        
        # Add port information from proper mapping
        port_info = self.port_intersections.get(intersection_id, [])
        if port_info:
            port_str = ", ".join(port_info)
            base_desc += f" - Provides access to {port_str}"
        
        return base_desc
    
    def get_edge_description(self, edge_id: str) -> str:
        """Get human-readable description of an edge.""" 
        if edge_id not in self.edges:
            return f"Unknown edge {edge_id}"
        
        edge_info = self.edges[edge_id]
        return f"{edge_id}: Road between {edge_info.tile_names[0]} and {edge_info.tile_names[1]}"
    
    def get_board_summary(self) -> str:
        """Get complete board summary with adjacency information."""
        lines = ["=== AXIAL COORDINATE BOARD ==="]
        
        # Sort tiles by distance from center, then by coordinate
        sorted_tiles = sorted(
            self.tiles.items(),
            key=lambda x: (self.get_distance(x[0], (0, 0)), x[0])
        )
        
        for coord, tile in sorted_tiles:
            q, r = coord
            
            # Basic tile info
            line = f"{tile.name} @({q},{r})"
            if tile.resource and tile.number:
                line += f": {tile.resource} {tile.number}"
            elif tile.resource:
                line += f": {tile.resource}"
                
            # Add neighbor info
            neighbor_names = []
            for nq, nr in tile.neighbors:
                if (nq, nr) in self.tiles:
                    neighbor_names.append(f"{self.tiles[(nq, nr)].name}@({nq},{nr})")
            
            if neighbor_names:
                line += f" [Adjacent: {', '.join(neighbor_names[:3])}{'...' if len(neighbor_names) > 3 else ''}]"
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def clear_action_mappings(self):
        """Clear action mappings."""
        self.action_mappings.clear()
    
    def register_action_mapping(self, action_index: int, description: str):
        """Register action mapping."""
        self.action_mappings[action_index] = description
    
    def get_action_description(self, action_index: int) -> Optional[str]:
        """Get action description."""
        return self.action_mappings.get(action_index)
    
    def find_action_by_description(self, description: str) -> Optional[int]:
        """Find action index by description."""
        for idx, desc in self.action_mappings.items():
            if desc == description:
                return idx
        return None
    
    def get_intersection_by_node_id(self, node_id: int) -> Optional[str]:
        """Get intersection description by Catanatron node ID."""
        intersection_id = self.node_to_intersection.get(node_id)
        if intersection_id:
            return self.get_intersection_description(intersection_id)
        return None
    
    def get_edge_by_edge_id(self, edge_id) -> Optional[str]:
        """Get edge description by Catanatron edge ID.""" 
        # Try to map edge ID to our edge system
        if isinstance(edge_id, (list, tuple)) and len(edge_id) >= 2:
            edge_key = tuple(sorted(edge_id[:2]))
            return self.edge_to_edge_info.get(edge_key)
        return None