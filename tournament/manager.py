"""
Tournament management system for running LLM Catan competitions.

This module provides the main tournament orchestration functionality,
handling multiple games, player management, and results collection.
"""

import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import random
from pathlib import Path

from catanatron import Game
from catanatron.models.player import Color
from catanbench.core.llm_player import LLMPlayer
from catanbench.utils.logging import setup_tournament_logging


class TournamentManager:
    """
    Manages tournaments between LLM players.
    
    This class orchestrates multiple games between different LLM players,
    collecting statistics and generating comprehensive reports.
    """
    
    def __init__(
        self, 
        name: str = "CatanBench Tournament",
        output_dir: str = "tournament_results",
        log_level: str = "INFO"
    ):
        """
        Initialize tournament manager.
        
        Args:
            name: Tournament name for identification
            output_dir: Directory to save results and logs
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.name = name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Tournament state
        self.players = {}  # name -> (llm_client, player_config)
        self.results = []
        self.current_tournament_id = None
        
        # Configuration
        self.config = {
            "games_per_matchup": 5,
            "timeout_per_game": 600,  # 10 minutes
            "shuffle_colors": True,
            "detailed_logging": True
        }
        
        # Set up logging
        self.logger = setup_tournament_logging(
            str(self.output_dir / "tournament.log"), 
            log_level
        )
        
        self.logger.info(f"Tournament manager initialized: {name}")
    
    def add_player(
        self, 
        name: str, 
        llm_client, 
        player_config: Optional[Dict[str, Any]] = None
    ):
        """
        Add a player to the tournament.
        
        Args:
            name: Player name for identification
            llm_client: LLM client instance
            player_config: Additional configuration for the player
        """
        config = player_config or {}
        self.players[name] = (llm_client, config)
        self.logger.info(f"Added player: {name} ({llm_client.model_name})")
    
    def run_tournament(
        self,
        games_per_matchup: int = 5,
        tournament_format: str = "round_robin",
        save_games: bool = True
    ) -> Dict[str, Any]:
        """
        Run a complete tournament between all added players.
        
        Args:
            games_per_matchup: Number of games to play per unique player combination
            tournament_format: Tournament format ("round_robin", "single_elimination")
            save_games: Whether to save detailed game logs
            
        Returns:
            Tournament results dictionary
        """
        if len(self.players) < 2:
            raise ValueError("Need at least 2 players for a tournament")
        
        self.current_tournament_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.config["games_per_matchup"] = games_per_matchup
        
        self.logger.info(f"Starting tournament: {self.name} (ID: {self.current_tournament_id})")
        self.logger.info(f"Players: {list(self.players.keys())}")
        self.logger.info(f"Format: {tournament_format}, Games per matchup: {games_per_matchup}")
        
        start_time = time.time()
        
        try:
            if tournament_format == "round_robin":
                results = self._run_round_robin_tournament(games_per_matchup, save_games)
            else:
                raise ValueError(f"Tournament format '{tournament_format}' not implemented")
            
            # Calculate final statistics
            tournament_duration = time.time() - start_time
            results["tournament_info"] = {
                "name": self.name,
                "id": self.current_tournament_id,
                "format": tournament_format,
                "games_per_matchup": games_per_matchup,
                "total_games": len(self.results),
                "duration_seconds": tournament_duration,
                "players": list(self.players.keys())
            }
            
            # Save results
            if save_games:
                self._save_tournament_results(results)
            
            self.logger.info(f"Tournament completed in {tournament_duration:.2f} seconds")
            return results
            
        except Exception as e:
            self.logger.error(f"Tournament failed: {e}", exc_info=True)
            raise
    
    def _run_round_robin_tournament(
        self, 
        games_per_matchup: int, 
        save_games: bool
    ) -> Dict[str, Any]:
        """
        Run a round-robin tournament where every player combination plays multiple games.
        
        Args:
            games_per_matchup: Number of games per unique player combination
            save_games: Whether to save detailed game information
            
        Returns:
            Tournament results
        """
        player_names = list(self.players.keys())
        total_games = 0
        
        # Generate all unique 4-player combinations
        if len(player_names) == 4:
            matchups = [player_names]
            total_games = games_per_matchup
        elif len(player_names) > 4:
            # For more than 4 players, we need to create different 4-player combinations
            from itertools import combinations
            matchups = list(combinations(player_names, 4))
            total_games = len(matchups) * games_per_matchup
        else:
            # For fewer than 4 players, add random players to fill slots
            matchups = [player_names + [f"Random_{i}" for i in range(4 - len(player_names))]]
            total_games = games_per_matchup
        
        self.logger.info(f"Total matchups: {len(matchups)}, Total games: {total_games}")
        
        game_results = []
        
        for matchup_idx, player_combo in enumerate(matchups):
            self.logger.info(f"Starting matchup {matchup_idx + 1}/{len(matchups)}: {player_combo}")
            
            for game_num in range(games_per_matchup):
                try:
                    game_result = self._play_single_game(
                        player_combo, 
                        matchup_idx, 
                        game_num,
                        save_games
                    )
                    game_results.append(game_result)
                    
                    # Log progress
                    completed_games = len(game_results)
                    progress = (completed_games / total_games) * 100
                    self.logger.info(f"Game {completed_games}/{total_games} completed ({progress:.1f}%)")
                    
                except Exception as e:
                    self.logger.error(f"Game failed in matchup {matchup_idx}, game {game_num}: {e}")
                    # Continue with next game instead of failing entire tournament
        
        # Analyze results
        analysis = self._analyze_tournament_results(game_results)
        
        return {
            "games": game_results,
            "analysis": analysis,
            "player_stats": self._calculate_player_statistics(game_results),
            "matchup_analysis": self._analyze_matchups(game_results)
        }
    
    def _play_single_game(
        self, 
        player_names: List[str], 
        matchup_idx: int, 
        game_num: int,
        save_detailed: bool = True
    ) -> Dict[str, Any]:
        """
        Play a single Catan game between the specified players.
        
        Args:
            player_names: List of player names (must be exactly 4)
            matchup_idx: Index of the current matchup
            game_num: Game number within the matchup
            save_detailed: Whether to save detailed game information
            
        Returns:
            Game result dictionary
        """
        game_id = f"M{matchup_idx:02d}_G{game_num:02d}"
        self.logger.info(f"Starting game {game_id}: {player_names}")
        
        colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
        if self.config["shuffle_colors"]:
            random.shuffle(colors)
        
        # Create players
        players = []
        player_info = []
        
        for i, player_name in enumerate(player_names):
            if player_name.startswith("Random_"):
                # Add random player for filling slots
                from catanatron.models.player import RandomPlayer
                player = RandomPlayer(colors[i])
                player_info.append({
                    "name": player_name,
                    "type": "random",
                    "color": colors[i].value,
                    "model": "RandomPlayer"
                })
            else:
                # Create LLM player
                llm_client, config = self.players[player_name]
                player = LLMPlayer(
                    color=colors[i],
                    llm_client=llm_client,
                    name=player_name,
                    **config
                )
                player_info.append({
                    "name": player_name,
                    "type": "llm",
                    "color": colors[i].value,
                    "model": llm_client.model_name
                })
            
            players.append(player)
        
        # Play the game
        start_time = time.time()
        try:
            game = Game(players)
            winner_color = game.play()
            game_duration = time.time() - start_time
            
            # Determine winner
            winner_name = None
            for info in player_info:
                if info["color"] == winner_color.value:
                    winner_name = info["name"]
                    break
            
            # Collect player performance stats
            player_stats = {}
            for player in players:
                if hasattr(player, 'get_performance_summary'):
                    stats = player.get_performance_summary()
                    player_stats[stats.get("player_name", "unknown")] = stats
            
            result = {
                "game_id": game_id,
                "matchup_index": matchup_idx,
                "game_number": game_num,
                "players": player_info,
                "winner": {
                    "name": winner_name,
                    "color": winner_color.value
                },
                "duration_seconds": game_duration,
                "player_performance": player_stats,
                "timestamp": datetime.now().isoformat()
            }
            
            if save_detailed:
                # Add more detailed game information if needed
                result["detailed_stats"] = {
                    "total_turns": getattr(game.state, 'num_turns', 0),
                    "final_scores": self._extract_final_scores(game)
                }
            
            self.logger.info(f"Game {game_id} completed: Winner {winner_name} ({winner_color.value}) in {game_duration:.2f}s")
            return result
            
        except Exception as e:
            game_duration = time.time() - start_time
            self.logger.error(f"Game {game_id} failed after {game_duration:.2f}s: {e}")
            
            return {
                "game_id": game_id,
                "matchup_index": matchup_idx,
                "game_number": game_num,
                "players": player_info,
                "winner": None,
                "duration_seconds": game_duration,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _extract_final_scores(self, game) -> Dict[str, int]:
        """Extract final victory point scores from the game."""
        scores = {}
        try:
            for color in [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]:
                from catanatron.state_functions import player_key
                player_state = game.state.player_state.get(player_key(game.state, color), {})
                vp = player_state.get("VICTORY_POINTS", 0)
                scores[color.value] = vp
        except Exception as e:
            self.logger.warning(f"Could not extract final scores: {e}")
        return scores
    
    def _analyze_tournament_results(self, game_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze overall tournament results."""
        total_games = len(game_results)
        successful_games = len([g for g in game_results if g.get("winner")])
        failed_games = total_games - successful_games
        
        # Win rates
        wins = {}
        for result in game_results:
            if result.get("winner"):
                winner = result["winner"]["name"]
                wins[winner] = wins.get(winner, 0) + 1
        
        # Average game duration
        durations = [g["duration_seconds"] for g in game_results]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "total_games": total_games,
            "successful_games": successful_games,
            "failed_games": failed_games,
            "success_rate": successful_games / total_games if total_games > 0 else 0,
            "win_counts": wins,
            "average_game_duration": avg_duration,
            "total_tournament_duration": sum(durations)
        }
    
    def _calculate_player_statistics(self, game_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate detailed statistics for each player."""
        player_stats = {}
        
        for result in game_results:
            for player_info in result["players"]:
                name = player_info["name"]
                if name not in player_stats:
                    player_stats[name] = {
                        "games_played": 0,
                        "wins": 0,
                        "win_rate": 0.0,
                        "avg_decision_time": 0.0,
                        "total_decision_time": 0.0,
                        "model": player_info.get("model", "unknown"),
                        "type": player_info.get("type", "unknown")
                    }
                
                player_stats[name]["games_played"] += 1
                
                if result.get("winner") and result["winner"]["name"] == name:
                    player_stats[name]["wins"] += 1
                
                # Add performance data if available
                perf_data = result.get("player_performance", {}).get(name, {})
                if perf_data:
                    player_stats[name]["avg_decision_time"] = perf_data.get("avg_decision_time", 0.0)
                    player_stats[name]["total_decision_time"] += perf_data.get("avg_decision_time", 0.0)
        
        # Calculate win rates
        for name, stats in player_stats.items():
            if stats["games_played"] > 0:
                stats["win_rate"] = stats["wins"] / stats["games_played"]
        
        return player_stats
    
    def _analyze_matchups(self, game_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze head-to-head matchup performance."""
        matchup_data = {}
        
        for result in game_results:
            players = [p["name"] for p in result["players"]]
            matchup_key = "_vs_".join(sorted(players))
            
            if matchup_key not in matchup_data:
                matchup_data[matchup_key] = {
                    "players": sorted(players),
                    "games": 0,
                    "wins": {player: 0 for player in players}
                }
            
            matchup_data[matchup_key]["games"] += 1
            if result.get("winner"):
                winner = result["winner"]["name"]
                if winner in matchup_data[matchup_key]["wins"]:
                    matchup_data[matchup_key]["wins"][winner] += 1
        
        return matchup_data
    
    def _save_tournament_results(self, results: Dict[str, Any]):
        """Save tournament results to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save complete results as JSON
        results_file = self.output_dir / f"tournament_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Save summary CSV for easy analysis
        try:
            import pandas as pd
            
            # Create game summary DataFrame
            game_data = []
            for game in results["games"]:
                game_data.append({
                    "game_id": game["game_id"],
                    "winner": game.get("winner", {}).get("name", "Failed"),
                    "winner_color": game.get("winner", {}).get("color", "None"),
                    "duration": game["duration_seconds"],
                    "players": ", ".join([p["name"] for p in game["players"]]),
                    "success": game.get("winner") is not None
                })
            
            df = pd.DataFrame(game_data)
            csv_file = self.output_dir / f"tournament_summary_{timestamp}.csv"
            df.to_csv(csv_file, index=False)
            
            self.logger.info(f"Results saved: {results_file}, {csv_file}")
            
        except ImportError:
            self.logger.warning("Pandas not available, skipping CSV export")
        except Exception as e:
            self.logger.error(f"Error saving CSV: {e}")
    
    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Get current tournament leaderboard."""
        if not self.results:
            return []
        
        # Calculate current standings
        stats = self._calculate_player_statistics(self.results)
        
        # Sort by win rate, then by wins
        leaderboard = []
        for name, stat in stats.items():
            leaderboard.append({
                "player": name,
                "model": stat["model"],
                "wins": stat["wins"],
                "games": stat["games_played"],
                "win_rate": stat["win_rate"],
                "avg_decision_time": stat["avg_decision_time"]
            })
        
        leaderboard.sort(key=lambda x: (x["win_rate"], x["wins"]), reverse=True)
        return leaderboard