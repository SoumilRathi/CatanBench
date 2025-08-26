"""
Test script for CatanBench - demonstrates basic functionality.

This script shows how to use the CatanBench system to run a simple
tournament between different LLM players and random players.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.llm_player import LLMPlayer
from models import OpenAIClient, ClaudeClient
from tournament.manager import TournamentManager
from catanatron.models.player import Color, RandomPlayer


class MockLLMClient:
    """Mock LLM client for testing without API calls."""
    
    def __init__(self, model_name: str = "mock-model"):
        self.model_name = model_name
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "avg_response_time": 0.0,
            "total_tokens_used": 0,
            "total_cost": 0.0
        }
    
    def query(self, prompt: str, temperature: float = 0.1, max_tokens=None, timeout: float = 30.0, **kwargs) -> str:
        """Return a mock JSON response for action selection."""
        import json
        import time
        import random
        
        # Simulate processing time
        time.sleep(random.uniform(0.1, 0.3))
        
        # Extract available action count from prompt
        action_count = prompt.count('"')  # Very rough estimate
        if action_count == 0:
            action_count = 5  # Default fallback
        
        # Return a random valid action selection
        action_index = random.randint(0, min(action_count - 1, 10))  # Cap at 10 actions
        
        response = {
            "action_index": action_index,
            "reasoning": f"Mock reasoning for action {action_index} from {self.model_name}"
        }
        
        # Update stats
        self.stats["total_requests"] += 1
        self.stats["successful_requests"] += 1
        
        return json.dumps(response)
    
    def get_model_info(self):
        return {
            "provider": "Mock",
            "model": self.model_name,
            "supports_json_mode": True,
            "context_length": 4096
        }


def test_basic_functionality():
    """Test basic functionality without API calls."""
    print("=== Testing Basic CatanBench Functionality ===\n")
    
    # Test mock LLM client
    print("1. Testing Mock LLM Client...")
    mock_client = MockLLMClient("test-gpt-4")
    response = mock_client.query("Test prompt with some actions: 0, 1, 2")
    print(f"   Mock response: {response}")
    print("   ✓ Mock client working\n")
    
    # Test LLM player creation
    print("2. Testing LLM Player Creation...")
    try:
        mock_player = LLMPlayer(
            color=Color.RED,
            llm_client=mock_client,
            name="TestPlayer"
        )
        print(f"   Created player: {mock_player}")
        print("   ✓ LLM Player creation working\n")
    except Exception as e:
        print(f"   ✗ Error creating LLM Player: {e}\n")
        return
    
    # Test tournament manager setup
    print("3. Testing Tournament Manager...")
    try:
        tournament = TournamentManager(
            name="Test Tournament",
            output_dir="test_results"
        )
        
        # Add mock players
        tournament.add_player("MockGPT", MockLLMClient("mock-gpt-4"))
        tournament.add_player("MockClaude", MockLLMClient("mock-claude-3"))
        
        print(f"   Tournament created with {len(tournament.players)} players")
        print("   ✓ Tournament Manager working\n")
    except Exception as e:
        print(f"   ✗ Error creating Tournament Manager: {e}\n")
        return
    
    # Test single game (with mock players)
    print("4. Testing Single Game Execution...")
    try:
        # Run a very quick test tournament
        results = tournament.run_tournament(
            games_per_matchup=1,  # Just one game for testing
            tournament_format="round_robin",
            save_games=True
        )
        
        print(f"   Tournament completed!")
        print(f"   Total games: {results['tournament_info']['total_games']}")
        print(f"   Duration: {results['tournament_info']['duration_seconds']:.2f}s")
        
        if results['games']:
            first_game = results['games'][0]
            winner = first_game.get('winner', {})
            print(f"   First game winner: {winner.get('name', 'Unknown')}")
        
        print("   ✓ Single game execution working\n")
        
    except Exception as e:
        print(f"   ✗ Error running tournament: {e}\n")
        import traceback
        traceback.print_exc()
        return
    
    print("=== All Basic Tests Passed! ===\n")
    
    # Show sample results
    print("Sample Tournament Results:")
    print(f"- Tournament: {results['tournament_info']['name']}")
    print(f"- Players: {', '.join(results['tournament_info']['players'])}")
    print(f"- Games Played: {results['tournament_info']['total_games']}")
    print(f"- Success Rate: {results['analysis']['success_rate']:.1%}")
    
    if results['analysis']['win_counts']:
        print("- Win Counts:")
        for player, wins in results['analysis']['win_counts'].items():
            print(f"  {player}: {wins}")


def test_with_real_apis():
    """Test with real API clients (requires API keys)."""
    print("\n=== Testing with Real API Clients ===")
    print("(This requires valid API keys in environment variables)\n")
    
    # Check for API keys
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_google = bool(os.getenv("GOOGLE_API_KEY"))
    
    print(f"OpenAI API Key: {'✓ Found' if has_openai else '✗ Missing'}")
    print(f"Anthropic API Key: {'✓ Found' if has_anthropic else '✗ Missing'}")
    print(f"Google API Key: {'✓ Found' if has_google else '✗ Missing'}")
    
    if not any([has_openai, has_anthropic, has_google]):
        print("\nNo API keys found. Set environment variables:")
        print("  export OPENAI_API_KEY=your_key_here")
        print("  export ANTHROPIC_API_KEY=your_key_here")
        print("  export GOOGLE_API_KEY=your_key_here")
        print("\nSkipping real API tests.")
        return
    
    print("\n🚨 Note: Real API tests will use actual API calls and may incur costs!")
    response = input("Continue with real API tests? (y/N): ")
    if response.lower() != 'y':
        print("Skipping real API tests.")
        return
    
    # Create tournament with real clients
    tournament = TournamentManager(
        name="Real API Test Tournament",
        output_dir="real_api_results"
    )
    
    # Add available API clients
    if has_openai:
        try:
            openai_client = OpenAIClient("gpt-3.5-turbo")  # Use cheaper model for testing
            tournament.add_player("GPT-3.5", openai_client)
            print("✓ Added OpenAI GPT-3.5-turbo")
        except Exception as e:
            print(f"✗ Failed to create OpenAI client: {e}")
    
    if has_anthropic:
        try:
            claude_client = ClaudeClient("claude-3-haiku-20240307")  # Use cheaper model
            tournament.add_player("Claude-3-Haiku", claude_client)
            print("✓ Added Claude 3 Haiku")
        except Exception as e:
            print(f"✗ Failed to create Claude client: {e}")
    
    # Run a minimal tournament
    if len(tournament.players) >= 1:
        print(f"\nRunning tournament with {len(tournament.players)} LLM player(s)...")
        
        try:
            results = tournament.run_tournament(
                games_per_matchup=1,  # Minimal for cost control
                save_games=True
            )
            
            print("\n✓ Real API tournament completed!")
            print(f"Duration: {results['tournament_info']['duration_seconds']:.2f}s")
            
            # Show cost information if available
            for game in results['games']:
                for player_name, perf in game.get('player_performance', {}).items():
                    if 'total_cost' in perf:
                        print(f"Player {player_name} cost: ${perf['total_cost']:.4f}")
            
        except Exception as e:
            print(f"✗ Real API tournament failed: {e}")
    else:
        print("No valid API clients created, skipping tournament.")


if __name__ == "__main__":
    print("CatanBench Test Suite\n")
    
    # Run basic tests first
    test_basic_functionality()
    
    # Optionally test real APIs
    test_with_real_apis()
    
    print("\n=== Test Suite Complete ===")
    print("If all tests passed, your CatanBench installation is working correctly!")
    print("\nNext steps:")
    print("1. Set up your API keys in .env file")
    print("2. Run: python examples/simple_tournament.py")
    print("3. Check the tournament_results/ directory for detailed results")