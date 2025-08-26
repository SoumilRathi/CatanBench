#!/usr/bin/env python3
"""
Visual tournament example with real-time game display.

This example shows games being played with visual feedback and
step-by-step progression display.
"""

import os
import sys
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tournament.manager import TournamentManager
from models import OpenAIClient, ClaudeClient

class VisualTournamentManager(TournamentManager):
    """Tournament manager with visual feedback."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_game_actions = []
        
    def _play_single_game(self, player_names, matchup_idx, game_num, save_detailed=True):
        """Override to add visual feedback during game play."""
        print("\n" + "="*60)
        print(f"🎮 STARTING GAME {matchup_idx + 1}-{game_num + 1}")
        print("="*60)
        
        # Show player lineup
        print("👥 Players:")
        for i, name in enumerate(player_names):
            print(f"  {i+1}. {name}")
        
        print("\n🎯 Game in progress...")
        
        # Play the game with the parent method
        result = super()._play_single_game(player_names, matchup_idx, game_num, save_detailed)
        
        # Show result
        if result.get("winner"):
            winner = result["winner"]["name"]
            duration = result["duration_seconds"]
            print(f"\n🏆 WINNER: {winner} (in {duration:.1f}s)")
        else:
            print(f"\n❌ Game failed: {result.get('error', 'Unknown error')}")
        
        print("-" * 60)
        return result


def run_visual_tournament():
    """Run a tournament with visual feedback."""
    print("🏰 CatanBench Visual Tournament")
    print("================================")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Create visual tournament manager
    tournament = VisualTournamentManager(
        name="Visual Demo Tournament",
        output_dir="visual_tournament_results"
    )
    
    # Add some mock players for demonstration
    class MockLLMClient:
        def __init__(self, name):
            self.model_name = name
            self.stats = {"total_requests": 0, "successful_requests": 0, "failed_requests": 0,
                         "total_response_time": 0.0, "avg_response_time": 0.0,
                         "total_tokens_used": 0, "total_cost": 0.0}
        
        def query(self, prompt, **kwargs):
            # Simulate thinking time
            time.sleep(0.1)
            import random
            import json
            return json.dumps({
                "action_index": random.randint(0, 5),
                "reasoning": f"Strategic decision by {self.model_name}"
            })
        
        def get_model_info(self):
            return {"provider": "Mock", "model": self.model_name}
    
    # Add players
    tournament.add_player("Strategic-AI", MockLLMClient("Strategic-AI"))
    tournament.add_player("Aggressive-Bot", MockLLMClient("Aggressive-Bot"))
    
    print(f"\n🤖 Added {len(tournament.players)} AI players")
    
    # Configure for visual display
    games_per_matchup = 2
    print(f"⚙️  Configuration: {games_per_matchup} games per matchup")
    
    print("\n🚀 Starting visual tournament...")
    print("   Watch the progress below!")
    
    # Run tournament
    try:
        results = tournament.run_tournament(
            games_per_matchup=games_per_matchup,
            save_games=True
        )
        
        # Show final results
        print("\n" + "="*60)
        print("🎉 TOURNAMENT COMPLETE!")
        print("="*60)
        
        info = results["tournament_info"]
        analysis = results["analysis"]
        
        print(f"📊 Games played: {info['total_games']}")
        print(f"⏱️  Duration: {info['duration_seconds']:.1f} seconds")
        print(f"✅ Success rate: {analysis['success_rate']:.1%}")
        
        print("\n🏆 FINAL LEADERBOARD:")
        leaderboard = tournament.get_leaderboard()
        for i, player in enumerate(leaderboard, 1):
            print(f"  {i}. {player['player']} - {player['wins']}/{player['games']} wins ({player['win_rate']:.1%})")
        
        # Show where results are saved
        print(f"\n📁 Results saved in: {tournament.output_dir}")
        print("   🎮 Game logs: visual_tournament_results/game_logs/")
        print("   📈 Data: visual_tournament_results/tournament_results_*.json")
        
        print("\n💡 To visualize individual games:")
        print("   python visualize_game.py --list --dir visual_tournament_results")
        
        return results
        
    except KeyboardInterrupt:
        print("\n⏸️  Tournament interrupted by user")
    except Exception as e:
        print(f"\n❌ Tournament failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_visual_tournament()