"""
Simple tournament example for CatanBench.

This example demonstrates how to set up and run a tournament
between different LLM players using the CatanBench framework.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tournament.manager import TournamentManager
from models import OpenAIClient, ClaudeClient, GeminiClient


def main():
    """Run a simple tournament between LLM players."""
    print("=== CatanBench Simple Tournament Example ===\n")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check available API keys
    print("Checking API availability...")
    apis = {
        "OpenAI": os.getenv("OPENAI_API_KEY"),
        "Anthropic": os.getenv("ANTHROPIC_API_KEY"), 
        "Google": os.getenv("GOOGLE_API_KEY")
    }
    
    available_apis = []
    for name, key in apis.items():
        if key:
            available_apis.append(name)
            print(f"✓ {name} API key found")
        else:
            print(f"✗ {name} API key missing")
    
    if not available_apis:
        print("\nNo API keys found! Please set up your .env file with API keys.")
        print("Copy .env.example to .env and add your keys.")
        return
    
    print(f"\nFound {len(available_apis)} API provider(s): {', '.join(available_apis)}\n")
    
    # Create tournament manager
    tournament = TournamentManager(
        name="Simple LLM Catan Tournament",
        output_dir="tournament_results"
    )
    
    # Add players based on available APIs
    players_added = 0
    
    if "OpenAI" in available_apis:
        try:
            gpt4_client = OpenAIClient("gpt-4o-mini")  # Cheaper model for testing
            tournament.add_player("GPT-4o-mini", gpt4_client)
            players_added += 1
            print("✓ Added GPT-4o-mini player")
        except Exception as e:
            print(f"✗ Failed to add OpenAI player: {e}")
    
    if "Anthropic" in available_apis:
        try:
            claude_client = ClaudeClient("claude-3-5-haiku-20241022")  # Cheaper model
            tournament.add_player("Claude-3.5-Haiku", claude_client)
            players_added += 1
            print("✓ Added Claude-3.5-Haiku player")
        except Exception as e:
            print(f"✗ Failed to add Claude player: {e}")
    
    if "Google" in available_apis:
        try:
            gemini_client = GeminiClient("gemini-1.5-flash")  # Fast model
            tournament.add_player("Gemini-1.5-Flash", gemini_client)
            players_added += 1
            print("✓ Added Gemini-1.5-Flash player")
        except Exception as e:
            print(f"✗ Failed to add Gemini player: {e}")
    
    # Add more players if we have less than 4
    if players_added < 4:
        remaining = 4 - players_added
        print(f"\nAdding {remaining} random player(s) to fill the game...")
        
        # Random players will be added automatically by the tournament manager
        # when there are fewer than 4 players
    
    if players_added == 0:
        print("No players could be created. Check your API keys and network connection.")
        return
    
    print(f"\nStarting tournament with {players_added} LLM player(s)...")
    
    # Configure tournament settings
    games_per_matchup = 3  # Keep it small for testing
    print(f"Games per matchup: {games_per_matchup}")
    print("Estimated cost: $0.10 - $0.50 (depending on models used)")
    
    # Confirm before running
    response = input("\nProceed with tournament? (y/N): ")
    if response.lower() != 'y':
        print("Tournament cancelled.")
        return
    
    # Run the tournament
    try:
        print("\n🎮 Starting tournament...")
        results = tournament.run_tournament(
            games_per_matchup=games_per_matchup,
            tournament_format="round_robin",
            save_games=True
        )
        
        print("\n🎉 Tournament completed successfully!")
        
        # Display results
        print("\n=== TOURNAMENT RESULTS ===")
        info = results["tournament_info"]
        analysis = results["analysis"]
        
        print(f"Tournament: {info['name']}")
        print(f"Duration: {info['duration_seconds']:.1f} seconds")
        print(f"Total Games: {info['total_games']}")
        print(f"Success Rate: {analysis['success_rate']:.1%}")
        
        print("\n=== LEADERBOARD ===")
        leaderboard = tournament.get_leaderboard()
        for i, player in enumerate(leaderboard, 1):
            print(f"{i}. {player['player']} ({player['model']})")
            print(f"   Wins: {player['wins']}/{player['games']} ({player['win_rate']:.1%})")
            if 'avg_decision_time' in player and player['avg_decision_time'] > 0:
                print(f"   Avg Decision Time: {player['avg_decision_time']:.2f}s")
        
        # Show cost information if available
        print("\n=== COST ANALYSIS ===")
        total_cost = 0.0
        for game in results["games"]:
            for player_name, perf in game.get("player_performance", {}).items():
                if perf and "total_cost" in perf and perf["total_cost"] > 0:
                    cost = perf["total_cost"]
                    total_cost += cost
                    print(f"{player_name}: ${cost:.4f}")
        
        if total_cost > 0:
            print(f"Total Estimated Cost: ${total_cost:.4f}")
        else:
            print("Cost information not available")
        
        # Show where results are saved
        print(f"\n📁 Detailed results saved in: tournament_results/")
        print("   - tournament_results_*.json (complete data)")
        print("   - tournament_summary_*.csv (game summary)")
        print("   - tournament.log (execution log)")
        
    except KeyboardInterrupt:
        print("\n⏸️  Tournament interrupted by user")
    except Exception as e:
        print(f"\n❌ Tournament failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()