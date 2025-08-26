"""
Simple real-time tournament manager using REST API polling instead of Socket.IO.

This module provides a simplified approach to real-time viewing without the complexity
of WebSocket connections. It uses simple HTTP polling every 15 seconds.
"""

import copy
import json
import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from aiohttp import web
import threading

from catanatron import Game
from catanatron.models.player import Color

from .manager import TournamentManager
from core.llm_player import LLMPlayer
from core.game_state import GameStateExtractor


class SimpleRealtimeTournamentManager(TournamentManager):
    """
    Simplified real-time tournament manager using REST API polling.
    
    Provides:
    - Simple HTTP endpoints for game state
    - Backend state logging for debugging  
    - No WebSocket complexity
    - 15-second polling from frontend
    """
    
    def __init__(
        self, 
        name: str = "Simple Real-time Tournament",
        output_dir: str = "tournament_results",
        log_level: str = "INFO",
        web_port: int = 8080
    ):
        """
        Initialize simple real-time tournament manager.
        
        Args:
            name: Tournament name for identification
            output_dir: Directory to save results and logs
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            web_port: Port for the web interface
        """
        super().__init__(name, output_dir, log_level)
        
        # Web interface configuration
        self.web_port = web_port
        
        # Real-time state tracking
        self.current_games = {}  # game_id -> game_state
        self.tournament_status = "not_started"
        self.tournament_info = {}
        
        # Web server
        self.app = web.Application()
        
        # Game state extractor for debugging logs
        self.game_state_extractor = GameStateExtractor()
        
        # Backend state logging
        self.backend_logger = self._setup_backend_logging()
        
        # Setup web routes
        self._setup_web_routes()
        
        self.logger.info(f"Simple real-time tournament manager initialized on port {web_port}")
    
    def _setup_backend_logging(self):
        """Setup dedicated backend state logging."""
        backend_log_path = self.output_dir / "backend_states.log"
        
        backend_logger = logging.getLogger('backend_states')
        backend_logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in backend_logger.handlers[:]:
            backend_logger.removeHandler(handler)
        
        handler = logging.FileHandler(backend_log_path)
        formatter = logging.Formatter(
            '%(asctime)s - BACKEND_STATE - %(message)s'
        )
        handler.setFormatter(formatter)
        backend_logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate logs
        backend_logger.propagate = False
        
        return backend_logger
    
    def _setup_web_routes(self):
        """Setup simple HTTP API routes."""
        # Main tournament interface
        self.app.router.add_get('/', self._serve_index)
        
        # Simple API endpoints
        self.app.router.add_get('/api/status', self._get_status)
        self.app.router.add_get('/api/games', self._get_games)
        self.app.router.add_get('/api/games/{game_id}', self._get_game_state)
        self.app.router.add_get('/api/leaderboard', self._get_leaderboard)
        
        # Catanatron UI compatibility endpoints
        self.app.router.add_post('/api/games', self._create_or_list_games)
        self.app.router.add_get('/api/games/{game_id}/states/latest', self._get_game_state_for_ui)
        self.app.router.add_get('/api/games/{game_id}/states/{state_index}', self._get_game_state_for_ui)
        self.app.router.add_post('/api/games/{game_id}/actions', self._post_game_action)
        
        # Enable CORS for frontend requests
        @web.middleware
        async def cors_middleware(request, handler):
            if request.method == 'OPTIONS':
                response = web.Response()
            else:
                response = await handler(request)
            
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = '*'
            return response
        
        self.app.middlewares.append(cors_middleware)
    
    async def _serve_index(self, request):
        """Serve the main tournament page with polling."""
        html_content = self._generate_polling_html()
        return web.Response(text=html_content, content_type='text/html')
    
    async def _get_status(self, request):
        """API endpoint for tournament status."""
        return web.json_response({
            'status': self.tournament_status,
            'tournament_info': self.tournament_info,
            'current_games': list(self.current_games.keys()),
            'timestamp': datetime.now().isoformat()
        })
    
    async def _get_games(self, request):
        """API endpoint for all current games."""
        # Create serializable version (exclude catanatron_state)
        serializable_games = {}
        for game_id, game_data in self.current_games.items():
            serializable_data = {k: v for k, v in game_data.items() if k != 'catanatron_state'}
            serializable_games[game_id] = serializable_data
        
        return web.json_response({
            'games': serializable_games,
            'timestamp': datetime.now().isoformat()
        })
    
    async def _get_game_state(self, request):
        """API endpoint for specific game state."""
        game_id = request.match_info['game_id']
        if game_id not in self.current_games:
            return web.json_response({'error': 'Game not found'}, status=404)
        
        game_data = self.current_games[game_id]
        catanatron_game = game_data.get('catanatron_game')
        
        if not catanatron_game:
            return web.json_response({
                'error': 'No game available',
                'game_id': game_id
            }, status=404)
        
        try:
            # Use GameEncoder properly with the Game object
            from catanatron.json import GameEncoder
            import json
            
            # This is the correct way to use GameEncoder
            json_string = json.dumps(catanatron_game, cls=GameEncoder)
            encoded_state = json.loads(json_string)
            
            # Add tournament-specific metadata
            encoded_state.update({
                'game_id': game_id,
                'tournament_game': True,
                'players': game_data.get('players', []),
                'player_info': game_data.get('player_info', []),
                'status': game_data.get('status', 'running'),
                'winner': game_data.get('winner'),
                'start_time': game_data.get('start_time'),
                'timestamp': datetime.now().isoformat()
            })
            
            return web.json_response(encoded_state)
            
        except Exception as e:
            self.logger.error(f"Failed to get game state for {game_id}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return web.json_response({
                'error': 'Failed to get game state',
                'details': str(e)
            }, status=500)
    
    async def _get_leaderboard(self, request):
        """API endpoint for tournament leaderboard."""
        try:
            leaderboard = self.get_leaderboard()
            return web.json_response({
                'leaderboard': leaderboard,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return web.json_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }, status=500)
    
    async def _create_or_list_games(self, request):
        """Catanatron UI compatibility - handle game creation requests."""
        self.logger.info(f"Game creation/listing requested from Catanatron UI")
        
        # Return the first available tournament game
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
    
    async def _get_game_state_for_ui(self, request):
        """Catanatron UI compatibility - get game state in UI format."""
        game_id = request.match_info['game_id']
        self.logger.info(f"UI requesting game state for: {game_id}")
        self.logger.info(f"Available games: {list(self.current_games.keys())}")
        
        if game_id not in self.current_games:
            self.logger.warning(f"Game {game_id} not found in current games")
            return web.json_response({
                'error': 'Game not found',
                'game_id': game_id,
                'available_games': list(self.current_games.keys())
            }, status=404)
        
        return await self._get_game_state(request)
    
    async def _post_game_action(self, request):
        """Catanatron UI compatibility - handle game actions (read-only for tournaments)."""
        game_id = request.match_info['game_id']
        
        try:
            await request.json() if request.body_exists else {}
        except:
            pass
        
        # Return current game state (tournaments are read-only)
        if game_id in self.current_games:
            return await self._get_game_state(request)
        else:
            return web.json_response({
                'error': 'Game not found'
            }, status=404)
    
    def start_web_server(self):
        """Start the web server in a background thread."""
        def run_server():
            try:
                web.run_app(
                    self.app, 
                    host='0.0.0.0', 
                    port=self.web_port,
                    handle_signals=False
                )
            except Exception as e:
                self.logger.error(f"Web server error: {e}")
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        time.sleep(2)  # Give server time to start
        self.logger.info(f"Simple web server started at http://localhost:{self.web_port}")
        return server_thread
    
    def run_tournament(
        self,
        games_per_matchup: int = 5,
        tournament_format: str = "round_robin",
        save_games: bool = True,
        start_web_server: bool = True
    ) -> Dict[str, Any]:
        """
        Run a tournament with simple real-time capabilities.
        """
        if start_web_server:
            self.start_web_server()
        
        self.tournament_status = "running"
        self.tournament_info = {
            "name": self.name,
            "format": tournament_format,
            "games_per_matchup": games_per_matchup,
            "players": list(self.players.keys()),
            "start_time": datetime.now().isoformat()
        }
        
        try:
            # Run tournament with state logging
            results = super().run_tournament(games_per_matchup, tournament_format, save_games)
            
            self.tournament_info.update(results.get("tournament_info", {}))
            self.tournament_status = "completed"
            
            return results
            
        except Exception as e:
            self.tournament_status = "failed"
            self.logger.error(f"Tournament failed: {e}")
            raise
    
    def _play_single_game(
        self, 
        player_names: List[str], 
        matchup_idx: int, 
        game_num: int,
        save_detailed: bool = True
    ) -> Dict[str, Any]:
        """
        Override to add state tracking and logging.
        """
        game_id = f"M{matchup_idx:02d}_G{game_num:02d}"
        
        # Initialize game tracking
        self.current_games[game_id] = {
            'game_id': game_id,
            'players': player_names,
            'status': 'starting',
            'start_time': datetime.now().isoformat(),
            'current_turn': 0,
            'catanatron_game': None  # Will store the Game object
        }
        
        self.logger.info(f"Starting game {game_id} with players: {player_names}")
        
        # Run game with state capture
        result = self._play_game_with_logging(
            player_names, matchup_idx, game_num, save_detailed
        )
        
        # Update final state
        self.current_games[game_id].update({
            'status': 'completed' if result.get('winner') else 'failed',
            'winner': result.get('winner'),
            'duration': result.get('duration_seconds'),
            'end_time': datetime.now().isoformat()
        })
        
        return result
    
    def _play_game_with_logging(
        self,
        player_names: List[str],
        matchup_idx: int,
        game_num: int,
        save_detailed: bool = True
    ) -> Dict[str, Any]:
        """Play a game with state logging for debugging."""
        game_id = f"M{matchup_idx:02d}_G{game_num:02d}"
        
        # Import required classes
        from catanatron import Game
        from catanatron.models.player import Color, RandomPlayer
        from core.llm_player import LLMPlayer
        import time
        from datetime import datetime
        
        colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
        
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
                self.current_games[game_id]['player_info'] = player_info
            
            # Create and run game with state capture
            game = Game(players)
            start_time = time.time()
            
            # Store initial game state immediately after game creation
            if game_id in self.current_games:
                self.current_games[game_id]['catanatron_game'] = game  # Store the Game object, not State
                self.logger.info(f"Captured initial game for game {game_id}")
            
            # Store original execute method for logging
            original_execute = game.execute
            action_count = 0
            
            def execute_with_logging(action):
                nonlocal action_count
                result = original_execute(action)
                action_count += 1
                
                # Log backend state every 2 actions for more frequent updates
                if action_count % 2 == 0 and game_id in self.current_games:
                    try:
                        # Keep game reference updated (no need to extract, just keep reference)
                        self.current_games[game_id]['catanatron_game'] = game
                        self.current_games[game_id]['current_turn'] = getattr(game.state, 'turn', action_count // 10)
                        
                        # Log detailed backend state for debugging
                        self._log_backend_state(game_id, game.state, action_count)
                        
                    except Exception as e:
                        self.logger.debug(f"State logging error: {e}")
                
                return result
            
            # Hook the execute method
            game.execute = execute_with_logging
            
            # Play the game
            winner_color = game.play()
            game_duration = time.time() - start_time
            
            # Final game update
            if game_id in self.current_games:
                self.current_games[game_id]['catanatron_game'] = game
                
                winner_info = None
                if winner_color:
                    winner_info = {
                        "name": next((info["name"] for info in player_info if info["color"] == winner_color.value), None),
                        "color": winner_color.value
                    }
                
                self.current_games[game_id]['winner'] = winner_info
                self.current_games[game_id]['status'] = 'completed' if winner_color else 'tie'
                self.current_games[game_id]['duration'] = game_duration
                
                # Final backend state log
                self._log_backend_state(game_id, game.state, action_count, final=True)
            
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
            raise
    
    def _log_backend_state(self, game_id: str, game_state, action_count: int, final: bool = False):
        """Log detailed backend state for debugging."""
        try:
            # Extract readable game state
            current_player = game_state.current_color()
            turn_num = getattr(game_state, 'turn', 0)
            
            # Get building counts for each player
            building_info = {}
            for color in [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]:
                from catanatron.state_functions import get_player_buildings
                from catanatron.models.enums import SETTLEMENT, CITY, ROAD
                
                settlements = list(get_player_buildings(game_state, color, SETTLEMENT))
                cities = list(get_player_buildings(game_state, color, CITY))
                roads = list(get_player_buildings(game_state, color, ROAD))
                
                building_info[color.value] = {
                    'settlements': len(settlements),
                    'cities': len(cities), 
                    'roads': len(roads),
                    'settlement_nodes': settlements[:3],  # First 3 for debugging
                    'road_edges': roads[:3]  # First 3 for debugging
                }
            
            # Create comprehensive log entry
            log_entry = {
                'game_id': game_id,
                'action_count': action_count,
                'turn': turn_num,
                'current_player': current_player.value,
                'buildings': building_info,
                'robber_position': getattr(game_state, 'robber_coordinate', None),
                'dice': getattr(game_state, 'dice', None),
                'final': final,
                'timestamp': datetime.now().isoformat()
            }
            
            # Log as JSON for easy parsing
            self.backend_logger.info(json.dumps(log_entry, indent=2))
            
        except Exception as e:
            self.logger.warning(f"Failed to log backend state: {e}")
    
    def _generate_polling_html(self) -> str:
        """Generate HTML page with 15-second polling."""
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple CatanBench Tournament</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            padding: 1rem;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1rem;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        
        .status-badge {
            display: inline-block;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
            margin-top: 0.5rem;
        }
        
        .status-not_started { background: #ffeaa7; color: #2d3436; }
        .status-running { background: #55a3ff; color: white; }
        .status-completed { background: #00b894; color: white; }
        .status-failed { background: #e17055; color: white; }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        
        .card h2 {
            margin-bottom: 1rem;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5rem;
        }
        
        .game-item {
            background: #f8f9fa;
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }
        
        .game-item.completed { border-left-color: #00b894; }
        .game-item.running { border-left-color: #55a3ff; }
        .game-item.failed { border-left-color: #e17055; }
        
        .last-update {
            color: #666;
            font-size: 0.9rem;
            margin-top: 1rem;
            text-align: center;
        }
        
        .polling-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-left: 0.5rem;
        }
        
        .polling-active { background: #00b894; }
        .polling-inactive { background: #ccc; }
        
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
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏰 Simple CatanBench Tournament</h1>
        <div class="status-badge" id="tournament-status">Not Started</div>
        <div class="last-update">
            Last Update: <span id="last-update">Never</span>
            <span class="polling-indicator" id="polling-indicator"></span>
        </div>
    </div>
    
    <div class="main-content">
        <div class="card">
            <h2>🎮 Current Games</h2>
            <div id="games-container">
                <div style="text-align: center; color: #666; padding: 2rem;">
                    No games running
                </div>
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
        // Simple polling every 15 seconds
        let pollingInterval;
        const pollingIndicator = document.getElementById('polling-indicator');
        const lastUpdateSpan = document.getElementById('last-update');
        const tournamentStatus = document.getElementById('tournament-status');
        const gamesContainer = document.getElementById('games-container');
        const leaderboardBody = document.getElementById('leaderboard-body');
        
        function updatePollingIndicator(active) {
            pollingIndicator.className = active ? 'polling-indicator polling-active' : 'polling-indicator polling-inactive';
        }
        
        function updateLastUpdate() {
            lastUpdateSpan.textContent = new Date().toLocaleTimeString();
        }
        
        async function fetchTournamentStatus() {
            updatePollingIndicator(true);
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // Update status
                tournamentStatus.textContent = data.status.replace('_', ' ');
                tournamentStatus.className = `status-badge status-${data.status}`;
                
                updateLastUpdate();
            } catch (error) {
                console.error('Failed to fetch status:', error);
            } finally {
                updatePollingIndicator(false);
            }
        }
        
        async function fetchGames() {
            try {
                const response = await fetch('/api/games');
                const data = await response.json();
                
                if (Object.keys(data.games).length === 0) {
                    gamesContainer.innerHTML = '<div style="text-align: center; color: #666; padding: 2rem;">No games running</div>';
                    return;
                }
                
                let gamesHtml = '';
                for (const [gameId, gameData] of Object.entries(data.games)) {
                    const statusClass = gameData.status || 'unknown';
                    const players = gameData.players ? gameData.players.join(', ') : 'Unknown players';
                    const winner = gameData.winner ? `🏆 Winner: ${gameData.winner.name || gameData.winner}` : '';
                    const duration = gameData.duration ? `⏱️ ${Math.round(gameData.duration)}s` : '';
                    
                    // Add visual game link if available
                    const visualLink = (gameData.status === 'running' || gameData.status === 'completed') ? 
                        `<div style="margin-top: 0.5rem;">
                            <a href="http://localhost:3002?gameId=${gameId}" target="_blank" 
                               style="color: #3498db; text-decoration: none; font-weight: bold; font-size: 0.9rem;"
                               onclick="checkCatanatronConnection(event, '${gameId}')">
                               🎮 Watch Visually
                            </a>
                        </div>` : '';
                    
                    gamesHtml += `
                        <div class="game-item ${statusClass}">
                            <div style="font-weight: bold; margin-bottom: 0.5rem;">${gameId}</div>
                            <div style="margin-bottom: 0.5rem;">Players: ${players}</div>
                            <div style="margin-bottom: 0.5rem;">Status: ${gameData.status || 'unknown'}</div>
                            ${winner ? `<div style="margin-bottom: 0.5rem;">${winner}</div>` : ''}
                            ${duration ? `<div style="color: #666; font-size: 0.9rem;">${duration}</div>` : ''}
                            ${visualLink}
                        </div>
                    `;
                }
                
                gamesContainer.innerHTML = gamesHtml;
            } catch (error) {
                console.error('Failed to fetch games:', error);
            }
        }
        
        async function fetchLeaderboard() {
            try {
                const response = await fetch('/api/leaderboard');
                const data = await response.json();
                
                if (data.leaderboard && data.leaderboard.length > 0) {
                    leaderboardBody.innerHTML = data.leaderboard.map((player, index) => `
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
                console.error('Failed to fetch leaderboard:', error);
            }
        }
        
        async function pollData() {
            await Promise.all([
                fetchTournamentStatus(),
                fetchGames(),
                fetchLeaderboard()
            ]);
        }
        
        // Start polling every 15 seconds
        function startPolling() {
            pollData(); // Initial load
            pollingInterval = setInterval(pollData, 15000); // 15 seconds
        }
        
        // Check Catanatron UI connection
        async function checkCatanatronConnection(event, gameId) {
            event.preventDefault();
            
            try {
                // Try to fetch from Catanatron UI to check if it's running
                const response = await fetch('http://localhost:3002', { mode: 'no-cors' });
                // If we get here, Catanatron UI is running
                window.open(`http://localhost:3002?gameId=${gameId}`, '_blank');
            } catch (error) {
                // Catanatron UI is not running
                alert(`Visual interface is not currently running.\\n\\nTo start the Catanatron visual interface:\\n\\n` +
                      `Option 1 (Docker): docker compose up\\n` +
                      `Option 2 (Manual): Install Node.js 24+ and run:\\n` +
                      `cd catanatron/ui && npm install && npm run start\\n\\n` +
                      `Then visit http://localhost:3002 to view Game ${gameId}`);
            }
        }
        
        // Start when page loads
        document.addEventListener('DOMContentLoaded', startPolling);
        
        // Show polling indicator on first load
        updatePollingIndicator(false);
    </script>
</body>
</html>
        '''