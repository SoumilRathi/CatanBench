"""
Real-time tournament management system with web interface and live game streaming.

This module extends the base TournamentManager to provide real-time viewing
capabilities, web interface integration, and live game state broadcasting.
"""

import asyncio
import copy
import json
import time
import logging
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
import websockets
import socketio
from aiohttp import web, WSMsgType

from catanatron import Game
from catanatron.models.player import Color

from .manager import TournamentManager
from core.llm_player import LLMPlayer
from core.game_state import GameStateExtractor


class RealTimeTournamentManager(TournamentManager):
    """
    Real-time tournament manager with web interface and live streaming capabilities.
    
    Extends the base tournament manager to provide:
    - Real-time web interface for viewing tournaments
    - Live game state broadcasting via WebSockets
    - Integration with catanatron's web GUI
    - Tournament progress tracking and visualization
    """
    
    def __init__(
        self, 
        name: str = "CatanBench Real-time Tournament",
        output_dir: str = "tournament_results",
        log_level: str = "INFO",
        web_port: int = 8080,
        enable_websockets: bool = True
    ):
        """
        Initialize real-time tournament manager.
        
        Args:
            name: Tournament name for identification
            output_dir: Directory to save results and logs
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            web_port: Port for the web interface
            enable_websockets: Whether to enable WebSocket broadcasting
        """
        super().__init__(name, output_dir, log_level)
        
        # Web interface configuration
        self.web_port = web_port
        self.enable_websockets = enable_websockets
        
        # Real-time state tracking
        self.current_games = {}  # game_id -> game_state
        self.game_updates = {}   # game_id -> [updates]
        self.connected_clients = set()
        self.tournament_status = "not_started"
        
        # WebSocket and web server
        self.sio = socketio.AsyncServer(cors_allowed_origins="*")
        self.app = web.Application()
        
        # Game state extractor for real-time updates
        self.game_state_extractor = GameStateExtractor()
        
        # Store reference to web server's event loop for cross-thread communication
        self.web_loop = None
        
        # Setup web routes first, then attach Socket.IO
        self._setup_web_routes()
        self._setup_socket_events()
        
        # Attach Socket.IO after routes are set up
        self.sio.attach(self.app)
        
        self.logger.info(f"Real-time tournament manager initialized on port {web_port}")
    
    def _safe_create_task(self, coro):
        """Safely schedule coroutine on the web server's event loop."""
        if self.web_loop is None:
            self.logger.warning("Web server loop not available, skipping broadcast")
            return
            
        try:
            # Schedule the coroutine on the web server's event loop from any thread
            future = asyncio.run_coroutine_threadsafe(coro, self.web_loop)
            # Don't wait for completion to avoid blocking
            self.logger.info("Scheduled async broadcast successfully")
        except Exception as e:
            self.logger.error(f"Could not schedule async task: {e}")
    
    def _setup_web_routes(self):
        """Setup web routes for the tournament interface."""
        # Serve static files
        self.app.router.add_get('/', self._serve_index)
        self.app.router.add_get('/tournament', self._serve_tournament_page)
        self.app.router.add_get('/api/tournament/status', self._get_tournament_status)
        self.app.router.add_get('/api/tournament/games', self._get_current_games)
        self.app.router.add_get('/api/tournament/leaderboard', self._get_leaderboard_api)
        
        # Catanatron UI compatibility endpoints
        self.app.router.add_post('/api/games', self._create_or_list_games)
        self.app.router.add_get('/api/games', self._list_games)
        self.app.router.add_get('/api/games/{game_id}/states/latest', self._get_game_state)
        self.app.router.add_get('/api/games/{game_id}/states/{state_index}', self._get_game_state_at_index)
        self.app.router.add_post('/api/games/{game_id}/actions', self._post_game_action)
        
        # Enable simple CORS middleware (Socket.IO handles its own CORS)
        @web.middleware
        async def cors_middleware(request, handler):
            if request.method == 'OPTIONS':
                response = web.Response()
            else:
                response = await handler(request)
            
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = '*'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response
        
        self.app.middlewares.append(cors_middleware)
    
    def _setup_socket_events(self):
        """Setup Socket.IO event handlers."""
        
        @self.sio.event
        async def connect(sid, environ):
            """Handle client connection."""
            self.connected_clients.add(sid)
            # self.logger.info(f"Client connected: {sid} (total: {len(self.connected_clients)})")
            
            # Send current tournament status
            await self.sio.emit('tournament_status', {
                'status': self.tournament_status,
                'tournament_info': getattr(self, 'tournament_info', {}),
                'current_games': list(self.current_games.keys())
            }, room=sid)
        
        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnection."""
            self.connected_clients.discard(sid)
            # self.logger.info(f"Client disconnected: {sid} (total: {len(self.connected_clients)})")
        
        @self.sio.event
        async def join_game(sid, data):
            """Handle client joining a specific game view."""
            game_id = data.get('game_id')
            if game_id in self.current_games:
                await self.sio.enter_room(sid, f"game_{game_id}")
                # Send serializable game data (exclude catanatron_state)
                game_data = {k: v for k, v in self.current_games[game_id].items() if k != 'catanatron_state'}
                await self.sio.emit('game_state', game_data, room=sid)
                self.logger.debug(f"Client {sid} joined game {game_id}")
        
        @self.sio.event
        async def leave_game(sid, data):
            """Handle client leaving a game view."""
            game_id = data.get('game_id')
            if game_id:
                await self.sio.leave_room(sid, f"game_{game_id}")
                self.logger.debug(f"Client {sid} left game {game_id}")
    
    async def _serve_index(self, request):
        """Serve the main tournament page."""
        html_content = self._generate_tournament_html()
        return web.Response(text=html_content, content_type='text/html')
    
    async def _serve_tournament_page(self, request):
        """Serve the tournament viewing page."""
        return await self._serve_index(request)
    
    async def _get_tournament_status(self, request):
        """API endpoint for tournament status."""
        return web.json_response({
            'status': self.tournament_status,
            'tournament_info': getattr(self, 'tournament_info', {}),
            'current_games': list(self.current_games.keys()),
            'connected_clients': len(self.connected_clients)
        })
    
    async def _get_current_games(self, request):
        """API endpoint for current games."""
        # Create serializable version of current games (exclude catanatron_state)
        serializable_games = {}
        for game_id, game_data in self.current_games.items():
            serializable_data = {k: v for k, v in game_data.items() if k != 'catanatron_state'}
            serializable_games[game_id] = serializable_data
        return web.json_response(serializable_games)
    
    async def _get_leaderboard_api(self, request):
        """API endpoint for tournament leaderboard."""
        try:
            leaderboard = self.get_leaderboard()
            return web.json_response(leaderboard)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def _get_game_state(self, request):
        """Catanatron UI compatibility - get latest game state."""
        game_id = request.match_info['game_id']
        if game_id not in self.current_games:
            return web.json_response({'error': 'Game not found'}, status=404)
        
        game_data = self.current_games[game_id]
        
        # Create a minimal Catanatron-compatible game state
        # This is a simplified state that the UI can display
        players = game_data.get('players', ['Player 1', 'Player 2', 'Player 3', 'Player 4'])
        player_info = game_data.get('player_info', [])
        colors = ['RED', 'BLUE', 'WHITE', 'ORANGE']
        
        # Try to extract real tiles from Catanatron state, otherwise use standard layout
        game_data_obj = self.current_games.get(game_id, {})
        catanatron_game_state = game_data_obj.get('catanatron_state')
        
        standard_tiles = []
        
        if catanatron_game_state and hasattr(catanatron_game_state, 'board'):
            try:
                # Extract real tiles from Catanatron board
                tile_id = 0
                if hasattr(catanatron_game_state.board, 'map') and hasattr(catanatron_game_state.board.map, 'tiles'):
                    for coordinate, tile in catanatron_game_state.board.map.tiles.items():
                        tile_data = {
                            "coordinate": list(coordinate) if isinstance(coordinate, tuple) else coordinate,
                            "tile": {
                                "id": tile_id,
                                "type": "DESERT" if not hasattr(tile, 'resource') or tile.resource is None else "RESOURCE_TILE"
                            }
                        }
                        
                        if hasattr(tile, 'resource') and tile.resource is not None:
                            tile_data["tile"]["resource"] = str(tile.resource).split('.')[-1] if hasattr(tile.resource, 'name') else str(tile.resource)
                        
                        if hasattr(tile, 'number') and tile.number is not None:
                            tile_data["tile"]["number"] = tile.number
                            
                        standard_tiles.append(tile_data)
                        tile_id += 1
                        
                # self.logger.info(f"Extracted {len(standard_tiles)} real tiles from Catanatron state")
                        
            except Exception as e:
                self.logger.warning(f"Failed to extract real tiles: {e}")
                standard_tiles = []
        
        # Fallback to standard board layout if no real tiles available
        if not standard_tiles:
            standard_tiles = [
                # Desert tile (center)
                {
                    "coordinate": [0, 0, 0],
                    "tile": {"id": 0, "type": "DESERT"}
                },
                # Resource tiles with proper structure
                {
                    "coordinate": [1, -1, 0],
                    "tile": {"id": 1, "type": "RESOURCE_TILE", "resource": "SHEEP", "number": 2}
                },
                {
                    "coordinate": [1, 0, -1],
                    "tile": {"id": 2, "type": "RESOURCE_TILE", "resource": "WHEAT", "number": 3}
                },
                {
                    "coordinate": [0, 1, -1],
                    "tile": {"id": 3, "type": "RESOURCE_TILE", "resource": "WOOD", "number": 4}
                },
                {
                    "coordinate": [-1, 1, 0],
                    "tile": {"id": 4, "type": "RESOURCE_TILE", "resource": "BRICK", "number": 5}
                },
                {
                    "coordinate": [-1, 0, 1],
                    "tile": {"id": 5, "type": "RESOURCE_TILE", "resource": "ORE", "number": 6}
                },
                {
                    "coordinate": [0, -1, 1],
                    "tile": {"id": 6, "type": "RESOURCE_TILE", "resource": "SHEEP", "number": 8}
                },
                {
                    "coordinate": [2, -2, 0],
                    "tile": {"id": 7, "type": "RESOURCE_TILE", "resource": "WOOD", "number": 9}
                },
                {
                    "coordinate": [2, -1, -1],
                    "tile": {"id": 8, "type": "RESOURCE_TILE", "resource": "WHEAT", "number": 10}
                },
                {
                    "coordinate": [1, 1, -2],
                    "tile": {"id": 9, "type": "RESOURCE_TILE", "resource": "WHEAT", "number": 11}
                },
                {
                    "coordinate": [0, 2, -2],
                    "tile": {"id": 10, "type": "RESOURCE_TILE", "resource": "BRICK", "number": 12}
                },
                {
                    "coordinate": [-1, 2, -1],
                    "tile": {"id": 11, "type": "RESOURCE_TILE", "resource": "ORE", "number": 3}
                },
                {
                    "coordinate": [-2, 2, 0],
                    "tile": {"id": 12, "type": "RESOURCE_TILE", "resource": "WOOD", "number": 4}
                },
                {
                    "coordinate": [-2, 1, 1],
                    "tile": {"id": 13, "type": "RESOURCE_TILE", "resource": "SHEEP", "number": 5}
                },
                {
                    "coordinate": [-2, 0, 2],
                    "tile": {"id": 14, "type": "RESOURCE_TILE", "resource": "BRICK", "number": 6}
                },
                {
                    "coordinate": [-1, -1, 2],
                    "tile": {"id": 15, "type": "RESOURCE_TILE", "resource": "ORE", "number": 8}
                },
                {
                    "coordinate": [0, -2, 2],
                    "tile": {"id": 16, "type": "RESOURCE_TILE", "resource": "WHEAT", "number": 9}
                },
                {
                    "coordinate": [1, -2, 1],
                    "tile": {"id": 17, "type": "RESOURCE_TILE", "resource": "WOOD", "number": 10}
                },
                {
                    "coordinate": [2, -2, 0],
                    "tile": {"id": 18, "type": "RESOURCE_TILE", "resource": "SHEEP", "number": 11}
                }
            ]
        
        # Extract nodes and edges with proper coordinate mapping from catanatron's board
        catanatron_nodes = {}
        catanatron_edges = {}
        
        if catanatron_game_state and hasattr(catanatron_game_state, 'board'):
            try:
                # Use Catanatron's GameEncoder to get proper coordinate mapping
                from catanatron.json import GameEncoder
                encoder = GameEncoder()
                
                # Extract the complete board structure with proper coordinates
                board_data = encoder.encode_board(catanatron_game_state.board)
                
                # Extract nodes with proper tile_coordinate and direction
                if 'nodes' in board_data:
                    for node_id, node_data in board_data['nodes'].items():
                        catanatron_nodes[int(node_id)] = {
                            "id": int(node_id),
                            "tile_coordinate": node_data.get('tile_coordinate', [0, 0, 0]),
                            "direction": node_data.get('direction', 'NORTH'),
                            "building": None,
                            "color": None
                        }
                
                # Extract edges with proper tile_coordinate and direction
                if 'edges' in board_data:
                    for edge_key, edge_data in board_data['edges'].items():
                        catanatron_edges[edge_key] = {
                            "id": edge_data.get('id', [0, 1]),
                            "tile_coordinate": edge_data.get('tile_coordinate', [0, 0, 0]), 
                            "direction": edge_data.get('direction', 'EAST'),
                            "color": None
                        }
                
                self.logger.info(f"Extracted {len(catanatron_nodes)} nodes and {len(catanatron_edges)} edges from GameEncoder")
                
            except Exception as e:
                self.logger.warning(f"Failed to use GameEncoder, falling back to manual extraction: {e}")
                
                # Fallback: Manual extraction from board structure
                board = catanatron_game_state.board
                
                # Extract nodes with coordinate mapping
                if hasattr(board, 'map') and hasattr(board.map, 'board_structure'):
                    # Try to get node coordinate mapping from board structure
                    for node_id in range(54):  # Standard Catan has 54 nodes
                        # Default fallback coordinates - we'll improve this if needed
                        tile_coord = [0, 0, 0]
                        direction = "NORTH"
                        
                        catanatron_nodes[node_id] = {
                            "id": node_id,
                            "tile_coordinate": tile_coord,
                            "direction": direction,
                            "building": None,
                            "color": None
                        }
                
                # Extract edges with coordinate mapping
                for edge_id in range(72):  # Standard Catan has 72 edges
                    edge_key = f"{edge_id},{edge_id+1}"
                    catanatron_edges[edge_key] = {
                        "id": [edge_id, edge_id+1],
                        "tile_coordinate": [0, 0, 0],
                        "direction": "EAST", 
                        "color": None
                    }
        else:
            # Complete fallback: Create minimal structure with coordinates
            for i in range(54):
                catanatron_nodes[i] = {
                    "id": i,
                    "tile_coordinate": [0, 0, 0],
                    "direction": "NORTH",
                    "building": None,
                    "color": None
                }
            for i in range(72):
                edge_key = f"{i},{i+1}"
                catanatron_edges[edge_key] = {
                    "id": [i, i+1],
                    "tile_coordinate": [0, 0, 0],
                    "direction": "EAST",
                    "color": None
                }
        
        # Extract real building data using catanatron's native coordinate system
        if catanatron_game_state:
            try:
                # Import required functions from catanatron
                from catanatron.state_functions import get_player_buildings
                from catanatron.models.enums import SETTLEMENT, CITY, ROAD
                from catanatron.models.player import Color
                
                all_colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
                buildings_found = {"settlements": 0, "cities": 0, "roads": 0}
                
                # Extract buildings using catanatron's native API and map directly
                for color in all_colors:
                    color_str = color.value
                    
                    # Get settlements - these are node IDs in catanatron's coordinate system
                    settlements = list(get_player_buildings(catanatron_game_state, color, SETTLEMENT))
                    for node_id in settlements:
                        # Use catanatron's actual node ID directly
                        if node_id in catanatron_nodes:
                            catanatron_nodes[node_id]["building"] = "SETTLEMENT"
                            catanatron_nodes[node_id]["color"] = color_str
                            buildings_found["settlements"] += 1
                        else:
                            # Create the node if it doesn't exist (edge case)
                            catanatron_nodes[node_id] = {
                                "id": node_id,
                                "building": "SETTLEMENT",
                                "color": color_str
                            }
                            buildings_found["settlements"] += 1
                    
                    # Get cities - these are also node IDs
                    cities = list(get_player_buildings(catanatron_game_state, color, CITY))
                    for node_id in cities:
                        if node_id in catanatron_nodes:
                            catanatron_nodes[node_id]["building"] = "CITY"
                            catanatron_nodes[node_id]["color"] = color_str
                            buildings_found["cities"] += 1
                        else:
                            # Create the node if it doesn't exist
                            catanatron_nodes[node_id] = {
                                "id": node_id,
                                "building": "CITY",
                                "color": color_str
                            }
                            buildings_found["cities"] += 1
                    
                    # Get roads - these are edge tuples (node_id1, node_id2)
                    roads = list(get_player_buildings(catanatron_game_state, color, ROAD))
                    for edge_tuple in roads:
                        if isinstance(edge_tuple, (tuple, list)) and len(edge_tuple) == 2:
                            node_id1, node_id2 = edge_tuple
                            # Create consistent edge key (smaller node ID first)
                            edge_key = f"{min(node_id1, node_id2)},{max(node_id1, node_id2)}"
                            
                            if edge_key in catanatron_edges:
                                catanatron_edges[edge_key]["color"] = color_str
                                buildings_found["roads"] += 1
                            else:
                                # Create the edge if it doesn't exist
                                catanatron_edges[edge_key] = {
                                    "id": [node_id1, node_id2],
                                    "color": color_str
                                }
                                buildings_found["roads"] += 1
                
                self.logger.info(f"Successfully extracted buildings: {buildings_found['settlements']} settlements, {buildings_found['cities']} cities, {buildings_found['roads']} roads")
                
                # Log examples for debugging
                built_nodes = [n for n in catanatron_nodes.values() if n["building"]][:3]
                built_edges = [e for e in catanatron_edges.values() if e["color"]][:3]
                if built_nodes:
                    self.logger.info(f"Example buildings: {built_nodes}")
                if built_edges:
                    self.logger.info(f"Example roads: {built_edges}")
                        
            except Exception as e:
                self.logger.error(f"Failed to extract buildings from game state: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        catanatron_state = {
            'game_id': game_id,
            'colors': colors[:len(players)],  # Required: array of all player colors
            'players': [
                {
                    'color': colors[i], 
                    'name': players[i] if i < len(players) else f'Player {i+1}',
                    'model': player_info[i]['model'] if i < len(player_info) else 'Unknown'
                } 
                for i in range(4)
            ],
            'board': {
                'tiles': standard_tiles,
                'roads': [],
                'settlements': [],
                'cities': []
            },
            'tiles': standard_tiles,  # Required: Board.tsx expects gameState.tiles directly
            'nodes': catanatron_nodes,  # Use catanatron's native node structure
            'edges': catanatron_edges,  # Use catanatron's native edge structure
            'adjacent_tiles': {},  # Required by GameState type
            'turn': 0,
            'phase': 'PLAY',
            'current_color': 'RED',  # Fixed: was 'current_player'
            'current_player_index': 0,
            'bot_colors': colors[:len(players)],  # All tournament players are bots
            'human_colors': [],  # No human players in tournaments
            'winner': game_data.get('winner'),
            'winning_color': None,
            'status': game_data.get('status', 'running'),
            'message': f'Tournament Game {game_id} - {game_data.get("status", "running").title()}',
            # Add additional required fields
            'dice': getattr(catanatron_game_state, 'dice', [1, 1]) if catanatron_game_state else [1, 1],
            'robber_coordinate': getattr(catanatron_game_state, 'robber_coordinate', [0, 0, 0]) if catanatron_game_state else [0, 0, 0],
            'actions': [],
            'current_playable_actions': [],  # Fixed: proper field name
            'is_initial_build_phase': False,
            'current_prompt': f'Tournament Game {game_id} in progress',
            # Player state in correct Catanatron format
            'player_state': {}
        }
        
        # Build proper player state with correct key format (P0, P1, P2, P3)
        player_colors = colors[:len(players)]
        for i, color in enumerate(player_colors):
            player_key = f'P{i}'  # UI expects P0, P1, P2, P3 format
            
            # Get real game data if available, otherwise use realistic starting data
            game_data = self.current_games.get(game_id, {})
            catanatron_game_state = game_data.get('catanatron_state')
            
            if catanatron_game_state and hasattr(catanatron_game_state, 'player_state'):
                # Use real Catanatron game state
                try:
                    catanatron_state['player_state'].update({
                        f'{player_key}_WOOD_IN_HAND': catanatron_game_state.player_state.get(f'P{i}_WOOD_IN_HAND', 0),
                        f'{player_key}_BRICK_IN_HAND': catanatron_game_state.player_state.get(f'P{i}_BRICK_IN_HAND', 0),
                        f'{player_key}_SHEEP_IN_HAND': catanatron_game_state.player_state.get(f'P{i}_SHEEP_IN_HAND', 0),
                        f'{player_key}_WHEAT_IN_HAND': catanatron_game_state.player_state.get(f'P{i}_WHEAT_IN_HAND', 0),
                        f'{player_key}_ORE_IN_HAND': catanatron_game_state.player_state.get(f'P{i}_ORE_IN_HAND', 0),
                        f'{player_key}_DEVELOPMENT_CARDS_IN_HAND': catanatron_game_state.player_state.get(f'P{i}_DEVELOPMENT_CARDS_IN_HAND', 0),
                        f'{player_key}_ACTUAL_VICTORY_POINTS': catanatron_game_state.player_state.get(f'P{i}_ACTUAL_VICTORY_POINTS', 2),
                        f'{player_key}_PLAYED_KNIGHT': catanatron_game_state.player_state.get(f'P{i}_PLAYED_KNIGHT', 0),
                        f'{player_key}_HAS_ARMY': catanatron_game_state.player_state.get(f'P{i}_HAS_ARMY', False),
                        f'{player_key}_LONGEST_ROAD_LENGTH': catanatron_game_state.player_state.get(f'P{i}_LONGEST_ROAD_LENGTH', 0),
                        f'{player_key}_HAS_ROAD': catanatron_game_state.player_state.get(f'P{i}_HAS_ROAD', False),
                        f'{player_key}_SETTLEMENTS_AVAILABLE': catanatron_game_state.player_state.get(f'P{i}_SETTLEMENTS_AVAILABLE', 5),
                        f'{player_key}_CITIES_AVAILABLE': catanatron_game_state.player_state.get(f'P{i}_CITIES_AVAILABLE', 4),
                        f'{player_key}_ROADS_AVAILABLE': catanatron_game_state.player_state.get(f'P{i}_ROADS_AVAILABLE', 15),
                        f'{player_key}_HAS_ROLLED': catanatron_game_state.player_state.get(f'P{i}_HAS_ROLLED', False)
                    })
                    
                    # Update robber position, dice, turn, and current color from real state
                    catanatron_state['robber_coordinate'] = getattr(catanatron_game_state, 'robber_coordinate', [0, 0, 0])
                    catanatron_state['dice'] = getattr(catanatron_game_state, 'dice', [1, 1])
                    catanatron_state['turn'] = getattr(catanatron_game_state, 'turn', 0)
                    catanatron_state['current_color'] = getattr(catanatron_game_state, 'current_color', colors[0]).value if hasattr(getattr(catanatron_game_state, 'current_color', colors[0]), 'value') else str(getattr(catanatron_game_state, 'current_color', colors[0]))
                    
                    continue  # Skip fallback data
                except Exception as e:
                    self.logger.warning(f"Failed to extract real player data for P{i}: {e}")
            
            # Fallback to realistic starting values (all players start with 2 VPs, no resources)
            catanatron_state['player_state'].update({
                f'{player_key}_WOOD_IN_HAND': 0,  # Start with no resources
                f'{player_key}_BRICK_IN_HAND': 0,  
                f'{player_key}_SHEEP_IN_HAND': 0,
                f'{player_key}_WHEAT_IN_HAND': 0,
                f'{player_key}_ORE_IN_HAND': 0,
                f'{player_key}_DEVELOPMENT_CARDS_IN_HAND': 0,
                f'{player_key}_ACTUAL_VICTORY_POINTS': 2,  # Standard starting VPs
                f'{player_key}_PLAYED_KNIGHT': 0,
                f'{player_key}_HAS_ARMY': False,
                f'{player_key}_LONGEST_ROAD_LENGTH': 0,
                f'{player_key}_HAS_ROAD': False,
                f'{player_key}_SETTLEMENTS_AVAILABLE': 5,  # Standard starting buildings
                f'{player_key}_CITIES_AVAILABLE': 4,
                f'{player_key}_ROADS_AVAILABLE': 15,
                f'{player_key}_HAS_ROLLED': False
            })
        
        # Debug final node structure
        # node_count = len(catanatron_state.get('nodes', {}))
        # edge_count = len(catanatron_state.get('edges', {}))
        # building_nodes = [node for node in catanatron_state.get('nodes', {}).values() if node.get('building')]
        # self.logger.info(f"Final structure: {node_count} nodes, {edge_count} edges, {len(building_nodes)} with buildings")
        # if building_nodes:
        #     self.logger.info(f"  Sample building node: {building_nodes[0]}")
        
        return web.json_response(catanatron_state)
    
    async def _get_game_state_at_index(self, request):
        """Catanatron UI compatibility - get game state at specific index."""
        game_id = request.match_info['game_id'] 
        state_index = request.match_info['state_index']
        
        if game_id not in self.current_games:
            return web.json_response({'error': 'Game not found'}, status=404)
            
        # Log the request for debugging
        self.logger.debug(f"Game state requested for {game_id} at index {state_index}")
        
        # For now, just return latest state regardless of index
        # In a full implementation, you'd store game history
        return await self._get_game_state(request)
    
    async def _create_or_list_games(self, request):
        """Catanatron UI compatibility - handle game creation requests."""
        # Log the request for debugging
        self.logger.info(f"Game creation/listing requested from {request.remote}")
        
        # Instead of creating a new game, return the first available tournament game
        if self.current_games:
            first_game_id = list(self.current_games.keys())[0]
            return web.json_response({
                'game_id': first_game_id,
                'message': 'Connected to tournament game'
            })
        else:
            return web.json_response({
                'error': 'No active tournament games',
                'message': 'Start a tournament to see games here'
            }, status=404)
    
    async def _list_games(self, request):
        """Catanatron UI compatibility - list available games."""
        # Log the request for debugging
        self.logger.info(f"Games listing requested from {request.remote}")
        
        games_list = []
        for game_id, game_data in self.current_games.items():
            games_list.append({
                'game_id': game_id,
                'status': game_data.get('status', 'unknown'),
                'players': game_data.get('players', []),
                'created_at': game_data.get('start_time')
            })
        return web.json_response(games_list)
    
    async def _post_game_action(self, request):
        """Catanatron UI compatibility - handle game actions (read-only for tournaments)."""
        game_id = request.match_info['game_id']
        # Log the action attempt for debugging
        try:
            await request.json() if request.body_exists else {}
            # self.logger.info(f"Action attempted on tournament game {game_id}")
        except:
            # self.logger.info(f"Action attempted on tournament game {game_id}")
            pass
        
        # Return the current game state instead of error to prevent UI crashes
        if game_id in self.current_games:
            # Return current state as if the action succeeded (but don't actually do anything)
            mock_request = type('MockRequest', (), {'match_info': {'game_id': game_id}})()
            return await self._get_game_state(mock_request)
        else:
            return web.json_response({
                'error': 'Game not found',
                'message': 'Tournament game not available'
            }, status=404)
    
    def start_web_server(self):
        """Start the web server in a background thread with fixed signal handling."""
        def run_server():
            # Create event loop and store reference for cross-thread communication
            self.web_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.web_loop)
            
            try:
                web.run_app(
                    self.app, 
                    host='0.0.0.0', 
                    port=self.web_port,
                    # access_log=self.logger,
                    handle_signals=False  # Fix: prevent signal handler errors in threads
                )
            except Exception as e:
                self.logger.error(f"Web server error: {e}")
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # Wait for the web loop to be set
        retries = 0
        while self.web_loop is None and retries < 50:  # 5 second timeout
            time.sleep(0.1)
            retries += 1
            
        if self.web_loop is None:
            self.logger.error("Failed to start web server event loop")
        else:
            self.logger.info(f"Web server started at http://localhost:{self.web_port}")
        return server_thread
    
    def run_tournament(
        self,
        games_per_matchup: int = 5,
        tournament_format: str = "round_robin",
        save_games: bool = True,
        start_web_server: bool = True
    ) -> Dict[str, Any]:
        """
        Run a tournament with real-time capabilities.
        
        Args:
            games_per_matchup: Number of games per unique player combination
            tournament_format: Tournament format ("round_robin", "single_elimination")
            save_games: Whether to save detailed game logs
            start_web_server: Whether to start the web server
            
        Returns:
            Tournament results dictionary
        """
        if start_web_server:
            self.start_web_server()
            time.sleep(2)  # Give server time to start
        
        self.tournament_status = "running"
        
        # Store tournament info for broadcasting
        self.tournament_info = {
            "name": self.name,
            "format": tournament_format,
            "games_per_matchup": games_per_matchup,
            "players": list(self.players.keys()),
            "start_time": datetime.now().isoformat()
        }
        
        self._safe_create_task(self._broadcast_tournament_status())
        
        try:
            # Run tournament with real-time updates
            results = super().run_tournament(games_per_matchup, tournament_format, save_games)
            
            # Update tournament info with results
            self.tournament_info.update(results.get("tournament_info", {}))
            self.tournament_status = "completed"
            
            # Broadcast tournament completion safely
            self._safe_create_task(self._broadcast_tournament_status())
            
            return results
            
        except Exception as e:
            self.tournament_status = "failed"
            self.logger.error(f"Tournament failed: {e}")
            self._safe_create_task(self._broadcast_tournament_status())
            raise
    
    def _play_single_game(
        self, 
        player_names: List[str], 
        matchup_idx: int, 
        game_num: int,
        save_detailed: bool = True
    ) -> Dict[str, Any]:
        """
        Override to add real-time game state broadcasting.
        """
        game_id = f"M{matchup_idx:02d}_G{game_num:02d}"
        
        # Initialize game tracking
        self.current_games[game_id] = {
            'game_id': game_id,
            'players': player_names,
            'status': 'starting',
            'start_time': datetime.now().isoformat(),
            'current_turn': 0,
            'game_state': None
        }

        # Broadcast the new game immediately so UI can display it
        self.logger.info(f"Creating game {game_id} with players: {player_names}")
        self._safe_create_task(self._broadcast_game_update(game_id))
        
        # Create a custom Game class that broadcasts updates
        result = self._play_game_with_streaming(
            player_names, matchup_idx, game_num, save_detailed
        )
        
        # Update final game state
        self.current_games[game_id].update({
            'status': 'completed' if result.get('winner') else 'failed',
            'winner': result.get('winner'),
            'duration': result.get('duration_seconds'),
            'end_time': datetime.now().isoformat()
        })
        
        # Broadcast final update safely
        self._safe_create_task(self._broadcast_game_update(game_id))
        
        return result
    
    def _extract_real_player_state(self, catanatron_state, colors):
        """Extract real player state from Catanatron game state."""
        real_player_data = {}
        
        try:
            # Extract player state from Catanatron's format
            for i, color in enumerate(colors):
                player_key = f'P{i}'
                
                # Get resource counts
                resources = {
                    'WOOD': catanatron_state.player_state.get(f'P{i}_WOOD_IN_HAND', 0),
                    'BRICK': catanatron_state.player_state.get(f'P{i}_BRICK_IN_HAND', 0),
                    'SHEEP': catanatron_state.player_state.get(f'P{i}_SHEEP_IN_HAND', 0),
                    'WHEAT': catanatron_state.player_state.get(f'P{i}_WHEAT_IN_HAND', 0),
                    'ORE': catanatron_state.player_state.get(f'P{i}_ORE_IN_HAND', 0),
                }
                
                real_player_data[player_key] = {
                    'resources': resources,
                    'development_cards': catanatron_state.player_state.get(f'P{i}_DEVELOPMENT_CARDS_IN_HAND', 0),
                    'victory_points': catanatron_state.player_state.get(f'P{i}_ACTUAL_VICTORY_POINTS', 2),  # Start at 2
                    'played_knight': catanatron_state.player_state.get(f'P{i}_PLAYED_KNIGHT', 0),
                    'has_army': catanatron_state.player_state.get(f'P{i}_HAS_ARMY', False),
                    'longest_road': catanatron_state.player_state.get(f'P{i}_LONGEST_ROAD_LENGTH', 0),
                    'has_longest_road': catanatron_state.player_state.get(f'P{i}_HAS_ROAD', False),
                    'settlements_available': catanatron_state.player_state.get(f'P{i}_SETTLEMENTS_AVAILABLE', 5),
                    'cities_available': catanatron_state.player_state.get(f'P{i}_CITIES_AVAILABLE', 4),
                    'roads_available': catanatron_state.player_state.get(f'P{i}_ROADS_AVAILABLE', 15),
                }
                
            return real_player_data
        except Exception as e:
            self.logger.warning(f"Failed to extract real player state: {e}")
            return {}

    def _extract_real_board_state(self, catanatron_state):
        """Extract real board state including buildings and roads."""
        try:
            # Extract settlements, cities, and roads from the game state
            settlements = []
            cities = []
            roads = []
            
            # Get buildings from nodes
            if hasattr(catanatron_state, 'board') and hasattr(catanatron_state.board, 'nodes'):
                for node_id, node in catanatron_state.board.nodes.items():
                    if hasattr(node, 'building') and node.building:
                        building_data = {
                            'id': node_id,
                            'type': node.building.name if hasattr(node.building, 'name') else str(node.building),
                            'color': node.building.color.value if hasattr(node.building, 'color') else None,
                            'coordinate': getattr(node, 'coordinate', [0, 0, 0])
                        }
                        
                        if building_data['type'] == 'SETTLEMENT':
                            settlements.append(building_data)
                        elif building_data['type'] == 'CITY':
                            cities.append(building_data)
            
            # Get roads from edges
            if hasattr(catanatron_state, 'board') and hasattr(catanatron_state.board, 'edges'):
                for edge_id, edge in catanatron_state.board.edges.items():
                    if hasattr(edge, 'building') and edge.building:
                        road_data = {
                            'id': edge_id,
                            'color': edge.building.color.value if hasattr(edge.building, 'color') else None,
                            'coordinate': getattr(edge, 'coordinate', [0, 0])
                        }
                        roads.append(road_data)
            
            return {
                'settlements': settlements,
                'cities': cities,
                'roads': roads,
                'robber_position': getattr(catanatron_state, 'robber_coordinate', [0, 0, 0])
            }
        except Exception as e:
            self.logger.warning(f"Failed to extract real board state: {e}")
            return {'settlements': [], 'cities': [], 'roads': [], 'robber_position': [0, 0, 0]}

    def _play_game_with_streaming(
        self,
        player_names: List[str],
        matchup_idx: int,
        game_num: int,
        save_detailed: bool = True
    ) -> Dict[str, Any]:
        """Play a game with real-time state streaming."""
        game_id = f"M{matchup_idx:02d}_G{game_num:02d}"
        
        # Import required classes
        from catanatron import Game
        from catanatron.models.player import Color, RandomPlayer
        from core.llm_player import LLMPlayer
        import time
        from datetime import datetime
        
        colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
        # Fixed: Always use consistent color assignment - no shuffling
        # if self.config.get("shuffle_colors", False):
        #     random.shuffle(colors)
        
        # Create players
        players = []
        player_info = []
        
        for i, player_name in enumerate(player_names):
            if player_name.startswith("Random_"):
                player = RandomPlayer(colors[i])
                players.append(player)
                player_info.append({
                    "name": player_name,
                    "type": "random",
                    "color": colors[i].value,
                    "model": "RandomPlayer"
                })
            else:
                llm_client, config = self.players[player_name]
                player = LLMPlayer(
                    color=colors[i],
                    llm_client=llm_client,
                    name=player_name,
                    **config
                )
                players.append(player)
                player_info.append({
                    "name": player_name,
                    "type": "llm",
                    "color": colors[i].value,
                    "model": llm_client.model_name if hasattr(llm_client, 'model_name') else 'unknown'
                })
        
        try:
            # Mark game as running and store player info
            if game_id in self.current_games:
                self.current_games[game_id]['status'] = 'running'
                self.current_games[game_id]['player_info'] = player_info  # Store model information
                self._safe_create_task(self._broadcast_game_update(game_id))
            
            # Create and run game with state capture
            game = Game(players)
            start_time = time.time()
            
            # Store original execute method
            original_execute = game.execute
            action_count = 0
            
            def execute_with_capture(action):
                nonlocal action_count
                result = original_execute(action)
                action_count += 1
                
                # Capture state on significant actions for real-time updates
                # Only update on meaningful actions to avoid spam while maintaining responsiveness
                if action_count % 1 == 0 and game_id in self.current_games:  # Update on every action
                    try:
                        # Store real game state with deep copy to prevent mutations
                        self.current_games[game_id]['catanatron_state'] = copy.deepcopy(game.state)
                        self.current_games[game_id]['current_turn'] = getattr(game.state, 'turn', action_count // 10)
                        
                        # Broadcast update
                        self._safe_create_task(self._broadcast_game_update(game_id))
                    except Exception as e:
                        self.logger.debug(f"State capture error: {e}")
                
                return result
            
            # Hook the execute method
            game.execute = execute_with_capture
            
            # Play the game
            winner_color = game.play()
            game_duration = time.time() - start_time
            
            # Final state update
            if game_id in self.current_games:
                self.current_games[game_id]['catanatron_state'] = copy.deepcopy(game.state)
                
                winner_info = None
                if winner_color:
                    winner_info = {
                        "name": next((info["name"] for info in player_info if info["color"] == winner_color.value), None),
                        "color": winner_color.value
                    }
                
                self.current_games[game_id]['winner'] = winner_info
                self.current_games[game_id]['status'] = 'completed' if winner_color else 'tie'
                self.current_games[game_id]['duration'] = game_duration
                self._safe_create_task(self._broadcast_game_update(game_id))
            
            # Build result
            result = {
                "game_id": game_id,
                "matchup_index": matchup_idx,
                "game_number": game_num,
                "players": player_info,
                "winner": winner_info,
                "duration_seconds": game_duration,
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Game {game_id} failed: {e}")
            if game_id in self.current_games:
                self.current_games[game_id]['status'] = 'failed'
                self._safe_create_task(self._broadcast_game_update(game_id))
            raise
    
    async def _broadcast_game_update(self, game_id: str):
        """Broadcast game state update to connected clients."""
        if not self.enable_websockets or game_id not in self.current_games:
            return
        
        try:
            game_data = self.current_games[game_id]
            
            # Broadcast to all clients for dashboard
            await self.sio.emit('game_update', {
                'game_id': game_id,
                'data': game_data
            })
            
            # Get the full Catanatron-compatible game state for UI updates
            try:
                # Create a mock request to get game state
                mock_request = type('MockRequest', (), {
                    'match_info': {'game_id': game_id}
                })()
                
                # Get the full game state that would be sent to Catanatron UI
                response = await self._get_game_state(mock_request)
                if hasattr(response, 'text'):
                    import json
                    full_game_state = json.loads(await response.text())
                    
                    # Broadcast full game state to trigger UI refresh
                    await self.sio.emit('game_state_update', {
                        'game_id': game_id,
                        'state': full_game_state
                    })
                    
                    # Also broadcast to game-specific room
                    await self.sio.emit('game_state', full_game_state, room=f"game_{game_id}")
                    
            except Exception as state_error:
                self.logger.warning(f"Could not broadcast full game state: {state_error}")
            
            self.logger.info(f"Broadcast game update for {game_id}: {game_data['status']} to {len(self.connected_clients)} clients")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting game update: {e}")
    
    async def _broadcast_tournament_status(self):
        """Broadcast tournament status update."""
        if not self.enable_websockets:
            return
        
        try:
            status_data = {
                'status': self.tournament_status,
                'tournament_info': getattr(self, 'tournament_info', {}),
                'current_games': list(self.current_games.keys()),
                'connected_clients': len(self.connected_clients)
            }
            await self.sio.emit('tournament_status', status_data)
            self.logger.info(f"Broadcast tournament status: {self.tournament_status} to {len(self.connected_clients)} clients")
        except Exception as e:
            self.logger.error(f"Error broadcasting tournament status: {e}")
    
    def _generate_tournament_html(self) -> str:
        """Generate the main tournament viewing HTML page."""
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CatanBench Real-time Tournament</title>
    <script src="https://cdn.socket.io/4.7.4/socket.io.min.js" 
            integrity="sha384-Gr6Lu2Ajx28mzwyVR8CFkULdCU7kMlZ9UthllibdOSo6qAiN+yXNHqtgdTvFXMT4" 
            crossorigin="anonymous"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            padding: 1rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .header h1 {
            text-align: center;
            color: #2c3e50;
            margin-bottom: 0.5rem;
        }
        
        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .status-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 0.8rem;
        }
        
        .status-not_started { background: #ffeaa7; color: #2d3436; }
        .status-running { background: #55a3ff; color: white; }
        .status-completed { background: #00b894; color: white; }
        .status-failed { background: #e17055; color: white; }
        
        .main-content {
            max-width: 1200px;
            margin: 2rem auto;
            padding: 0 1rem;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
        }
        
        .card h2 {
            margin-bottom: 1rem;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5rem;
        }
        
        .games-grid {
            display: grid;
            gap: 1rem;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        }
        
        .game-card {
            background: linear-gradient(135deg, #74b9ff, #0984e3);
            color: white;
            padding: 1rem;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        
        .game-card:hover {
            transform: translateY(-2px);
        }
        
        .game-id {
            font-weight: bold;
            font-size: 1.1rem;
            margin-bottom: 0.5rem;
        }
        
        .game-players {
            font-size: 0.9rem;
            opacity: 0.9;
            margin-bottom: 0.5rem;
        }
        
        .game-status {
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 12px;
            background: rgba(255,255,255,0.2);
            font-size: 0.8rem;
        }
        
        .leaderboard-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .leaderboard-table th,
        .leaderboard-table td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        .leaderboard-table th {
            background: #f8f9fa;
            font-weight: bold;
            color: #2c3e50;
        }
        
        .leaderboard-table tr:nth-child(even) {
            background: #f8f9fa;
        }
        
        .catanatron-link {
            display: block;
            margin-top: 1rem;
            padding: 0.75rem;
            background: #00b894;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            text-align: center;
            font-weight: bold;
        }
        
        .catanatron-link:hover {
            background: #00a085;
        }
        
        .catanatron-info {
            margin-top: 1rem;
            padding: 1rem;
            background: #f8f9fa;
            border-radius: 6px;
            border-left: 4px solid #3498db;
        }
        
        .catanatron-info h3 {
            margin-bottom: 0.5rem;
            color: #2c3e50;
        }
        
        .catanatron-info ol {
            margin: 0.5rem 0;
            padding-left: 1.5rem;
        }
        
        .catanatron-info code {
            background: #e9ecef;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.85em;
        }
        
        .connection-status {
            font-size: 0.9rem;
        }
        
        .connected { color: #00b894; }
        .disconnected { color: #e17055; }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
                gap: 1rem;
            }
            
            .status-bar {
                flex-direction: column;
                gap: 0.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏰 CatanBench Real-time Tournament</h1>
        <div class="status-bar">
            <div>
                <span class="status-badge" id="tournament-status">Not Started</span>
            </div>
            <div class="connection-status">
                <span id="connection-status" class="disconnected">Disconnected</span>
                | <span id="client-count">0</span> viewers
            </div>
        </div>
    </div>
    
    <div class="main-content">
        <div class="card">
            <h2>🎮 Current Games</h2>
            <div id="games-container" class="games-grid">
                <div style="text-align: center; color: #666; padding: 2rem;">
                    No games running
                </div>
            </div>
            
            <div class="catanatron-info">
                <h3>🎮 Visual Game Interface</h3>
                <p>To view games with full visual interface:</p>
                <ol>
                    <li><strong>Docker (Recommended):</strong><br>
                        Run <code>docker compose up</code> in project directory<br>
                        Then visit <a href="http://localhost:3002" target="_blank">localhost:3002</a>
                    </li>
                    <li><strong>Manual Setup:</strong><br>
                        Install Node.js 24+, then:<br>
                        <code>cd catanatron/ui && npm install && npm run start</code>
                    </li>
                </ol>
                <a href="#" onclick="checkCatanatronStatus()" class="catanatron-link">
                    🔍 Check Visual GUI Status
                </a>
            </div>
        </div>
        
        <div class="card">
            <h2>🏆 Leaderboard</h2>
            <div id="leaderboard-container">
                <table class="leaderboard-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Player</th>
                            <th>Wins</th>
                            <th>Games</th>
                            <th>Win Rate</th>
                        </tr>
                    </thead>
                    <tbody id="leaderboard-body">
                        <tr>
                            <td colspan="5" style="text-align: center; color: #666;">
                                No data available
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // Initialize Socket.IO connection
        console.log('Socket.IO library loaded:', typeof io);
        const socket = io();
        
        // DOM elements
        const tournamentStatus = document.getElementById('tournament-status');
        const connectionStatus = document.getElementById('connection-status');
        const clientCount = document.getElementById('client-count');
        const gamesContainer = document.getElementById('games-container');
        const leaderboardBody = document.getElementById('leaderboard-body');
        
        // Connection status
        socket.on('connect', () => {
            connectionStatus.textContent = 'Connected';
            connectionStatus.className = 'connected';
            console.log('Connected to tournament server');
        });
        
        socket.on('connect_error', (error) => {
            console.error('Connection failed:', error);
            connectionStatus.textContent = 'Connection Failed';
            connectionStatus.className = 'disconnected';
        });
        
        socket.on('disconnect', () => {
            connectionStatus.textContent = 'Disconnected';
            connectionStatus.className = 'disconnected';
            console.log('Disconnected from tournament server');
        });
        
        // Tournament status updates
        socket.on('tournament_status', (data) => {
            console.log('Tournament status:', data);
            updateTournamentStatus(data.status);
            clientCount.textContent = data.connected_clients || 0;
        });
        
        // Game updates
        socket.on('game_update', (data) => {
            console.log('Game update received:', data);
            updateGameDisplay(data.game_id, data.data);
        });
        
        // Game state updates (for real-time Catanatron UI refresh)
        socket.on('game_state_update', (data) => {
            console.log('Game state update received:', data);
            // Store the latest game state for polling
            window.latestGameState = data.state;
            window.lastUpdateTime = Date.now();
            
            // Trigger custom event for advanced refresh mechanisms
            if (window.location.hostname === 'localhost' && window.location.port === '3002') {
                window.dispatchEvent(new CustomEvent('gameStateUpdate', {
                    detail: { gameId: data.game_id, state: data.state }
                }));
            }
        });
        
        // Auto-refresh mechanism for Catanatron UI
        if (window.location.hostname === 'localhost' && window.location.port === '3002') {
            console.log('Setting up auto-refresh for Catanatron UI');
            
            // Method 1: Simple page refresh when updates occur
            let lastRefresh = 0;
            setInterval(() => {
                if (window.lastUpdateTime && window.lastUpdateTime > lastRefresh && Date.now() - window.lastUpdateTime < 10000) {
                    console.log('Refreshing Catanatron UI with new game state');
                    lastRefresh = Date.now();
                    window.location.reload();
                }
            }, 3000); // Check every 3 seconds
            
            // Method 2: Try to intercept and refresh React state (more advanced)
            // This attempts to trigger a re-render by dispatching a custom event
            window.addEventListener('gameStateUpdate', (event) => {
                console.log('Game state update event received', event.detail);
                // Dispatch a fake storage event to trigger React re-renders
                window.dispatchEvent(new StorageEvent('storage', {
                    key: 'gameStateUpdate',
                    newValue: JSON.stringify(event.detail)
                }));
            });
        }
        
        // Additional debugging
        socket.onAny((eventName, ...args) => {
            console.log('Socket.IO event:', eventName, args);
        });
        
        // Functions
        function updateTournamentStatus(status) {
            tournamentStatus.textContent = status.replace('_', ' ');
            tournamentStatus.className = `status-badge status-${status}`;
        }
        
        function updateGameDisplay(gameId, gameData) {
            const gameElement = document.getElementById(`game-${gameId}`) || createGameElement(gameId);
            
            gameElement.innerHTML = `
                <div class="game-id">${gameData.game_id}</div>
                <div class="game-players">Players: ${gameData.players.join(', ')}</div>
                <div class="game-status">${gameData.status}</div>
            `;
            
            if (gameData.winner) {
                gameElement.innerHTML += `<div style="margin-top: 0.5rem;">🏆 Winner: ${gameData.winner.name || gameData.winner}</div>`;
            }
            
            // Add visual game link if available
            if (gameData.status === 'running' || gameData.status === 'completed') {
                gameElement.innerHTML += `<div style="margin-top: 0.5rem;">
                    <a href="http://localhost:3002?gameId=${gameId}" target="_blank" 
                       style="color: white; text-decoration: underline; font-size: 0.8rem;">
                       🎮 Watch Visually
                    </a>
                </div>`;
            }
        }
        
        function createGameElement(gameId) {
            const gameElement = document.createElement('div');
            gameElement.className = 'game-card';
            gameElement.id = `game-${gameId}`;
            gameElement.onclick = () => viewGame(gameId);
            
            // Clear "no games" message if it exists
            if (gamesContainer.children.length === 1 && gamesContainer.firstElementChild.textContent.includes('No games')) {
                gamesContainer.innerHTML = '';
            }
            
            gamesContainer.appendChild(gameElement);
            return gameElement;
        }
        
        function viewGame(gameId) {
            socket.emit('join_game', { game_id: gameId });
            // Try to open Catanatron GUI or show instructions
            checkCatanatronStatus(gameId);
        }
        
        async function checkCatanatronStatus(gameId = null) {
            try {
                const response = await fetch('http://localhost:3002', { mode: 'no-cors' });
                // If we get here, Catanatron is running
                window.open('http://localhost:3002', '_blank');
                if (gameId) {
                    alert(`Game ${gameId} - Visual interface opened in new tab`);
                }
            } catch (error) {
                // Catanatron GUI is not running
                const message = gameId 
                    ? `Game ${gameId} is running, but visual GUI is not available.` 
                    : 'Visual GUI is not currently running.';
                    
                alert(`${message}\n\nTo start visual interface:\n\n` +
                      `Option 1 (Docker): docker compose up\n` +
                      `Option 2 (Manual): Install Node.js 24+ and run:\n` +
                      `cd catanatron/ui && npm install && npm run start`);
            }
        }
        
        // Load initial data
        async function loadCurrentGames() {
            try {
                const response = await fetch('/api/tournament/games');
                const games = await response.json();
                console.log('Current games from API:', games);
                
                // Update games display
                for (const [gameId, gameData] of Object.entries(games)) {
                    updateGameDisplay(gameId, gameData);
                }
            } catch (error) {
                console.error('Error loading current games:', error);
            }
        }
        
        async function loadLeaderboard() {
            try {
                const response = await fetch('/api/tournament/leaderboard');
                const leaderboard = await response.json();
                
                if (leaderboard.length > 0) {
                    leaderboardBody.innerHTML = leaderboard.map((player, index) => `
                        <tr>
                            <td>${index + 1}</td>
                            <td>${player.player}</td>
                            <td>${player.wins}</td>
                            <td>${player.games}</td>
                            <td>${(player.win_rate * 100).toFixed(1)}%</td>
                        </tr>
                    `).join('');
                }
            } catch (error) {
                console.error('Error loading leaderboard:', error);
            }
        }
        
        // Refresh data periodically
        setInterval(() => {
            loadLeaderboard();
            loadCurrentGames();
        }, 5000);
        
        // Load initial data
        loadLeaderboard();
        loadCurrentGames();
    </script>
</body>
</html>
        ''' 