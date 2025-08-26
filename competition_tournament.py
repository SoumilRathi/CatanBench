"""
Competition tournament for comparing LLM performance at Catan.

This script runs a single round-robin tournament between GPT-5, Gemini 2.5 Pro, Claude Sonnet 4, 
and Kimi K2 with 3 games per matchup to establish win rates and rankings.
"""

import os
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tournament.manager import TournamentManager
from models import GPT5Client, ClaudeSonnet4Client, Gemini25ProClient, KimiK2Client


def extract_game_results_with_scores(results):
    """Extract game results with proper victory point scoring and tie handling."""
    enhanced_games = []
    
    for game in results["games"]:
        # Get final scores if available
        final_scores = {}
        if "detailed_stats" in game and "final_scores" in game["detailed_stats"]:
            final_scores = game["detailed_stats"]["final_scores"]
        
        # Map colors to player names
        color_to_player = {p["color"]: p["name"] for p in game["players"]}
        
        # Extract victory points for each player
        player_vp = {}
        for color, score in final_scores.items():
            if color in color_to_player:
                player_vp[color_to_player[color]] = score
        
        # Determine winner based on highest VP (or game winner if VP not available)
        if player_vp:
            max_vp = max(player_vp.values())
            winners = [player for player, vp in player_vp.items() if vp == max_vp]
            
            if len(winners) == 1:
                winner = winners[0]
                is_tie = False
            else:
                winner = winners  # List of tied players
                is_tie = True
        else:
            # Fallback to game winner - check for tie in winner info
            winner_info = game.get("winner")
            if winner_info:
                if winner_info.get("is_tie", False):
                    winner = winner_info.get("name") if isinstance(winner_info.get("name"), list) else [winner_info.get("name")]
                    is_tie = True
                else:
                    winner = winner_info.get("name") if isinstance(winner_info.get("name"), str) else winner_info["name"]
                    is_tie = False
            else:
                winner = None
                is_tie = False
        
        enhanced_game = {
            **game,
            "final_vp_scores": player_vp,
            "determined_winner": winner,
            "is_tie": is_tie,
            "max_vp": max(player_vp.values()) if player_vp else 0
        }
        enhanced_games.append(enhanced_game)
    
    return enhanced_games


def create_head_to_head_matrix(enhanced_games, players):
    """Create head-to-head win matrix between all players."""
    n_players = len(players)
    h2h_matrix = np.zeros((n_players, n_players))
    player_to_idx = {player: i for i, player in enumerate(players)}
    
    for game in enhanced_games:
        determined_winner = game["determined_winner"]
        is_tie = game["is_tie"]
        
        if determined_winner:
            if is_tie and isinstance(determined_winner, list):
                # Handle tie - give partial wins to each tied player
                tied_players = determined_winner
                for winner in tied_players:
                    winner_idx = player_to_idx[winner]
                    # Add partial wins against each non-tied opponent
                    for player_info in game["players"]:
                        opponent = player_info["name"]
                        if opponent not in tied_players:
                            opponent_idx = player_to_idx[opponent]
                            h2h_matrix[winner_idx][opponent_idx] += (1.0 / len(tied_players))
            elif not is_tie:
                # Single winner
                winner = determined_winner
                winner_idx = player_to_idx[winner]
                # Add wins against each opponent in this game
                for player_info in game["players"]:
                    opponent = player_info["name"]
                    if opponent != winner:
                        opponent_idx = player_to_idx[opponent]
                        h2h_matrix[winner_idx][opponent_idx] += 1
    
    return h2h_matrix, players


def create_tournament_visualizations(results, player_stats, elo_ratings, timestamp):
    """Create comprehensive tournament visualizations."""
    # Set up the plotting style
    plt.style.use('default')
    sns.set_palette("husl")
    
    # Get enhanced game results
    enhanced_games = extract_game_results_with_scores(results)
    players = list(player_stats.keys())
    
    # Create visualization directory
    vis_dir = Path("tournament_results") / "visualizations"
    vis_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Head-to-Head Matrix
    plt.figure(figsize=(10, 8))
    h2h_matrix, matrix_players = create_head_to_head_matrix(enhanced_games, players)
    
    # Create heatmap
    sns.heatmap(h2h_matrix, annot=True, fmt='.0f', cmap='Blues',
                xticklabels=matrix_players, yticklabels=matrix_players,
                cbar_kws={'label': 'Wins'})
    plt.title('Head-to-Head Win Matrix', fontsize=16, fontweight='bold')
    plt.xlabel('Opponent', fontsize=12)
    plt.ylabel('Winner', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(vis_dir / f"head_to_head_matrix_{timestamp}.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. Win Rate Comparison
    plt.figure(figsize=(12, 7))
    win_rates = [player_stats[player]["win_rate"] * 100 for player in players]
    games_played = [player_stats[player]["games_played"] for player in players]
    
    bars = plt.bar(players, win_rates, color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
    plt.title('Win Rate by Player', fontsize=16, fontweight='bold')
    plt.xlabel('Player', fontsize=12)
    plt.ylabel('Win Rate (%)', fontsize=12)
    plt.ylim(0, 100)
    
    # Add value labels on bars
    for i, (bar, rate, games) in enumerate(zip(bars, win_rates, games_played)):
        plt.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
                f'{rate:.1f}%\n({player_stats[players[i]]["wins"]}/{games})',
                ha='center', va='bottom', fontweight='bold')
    
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(vis_dir / f"win_rates_{timestamp}.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. ELO Ratings
    plt.figure(figsize=(12, 7))
    elo_values = [elo_ratings[player] for player in players]
    bars = plt.bar(players, elo_values, color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
    plt.title('Final ELO Ratings', fontsize=16, fontweight='bold')
    plt.xlabel('Player', fontsize=12)
    plt.ylabel('ELO Rating', fontsize=12)
    plt.axhline(y=1500, color='red', linestyle='--', alpha=0.7, label='Starting ELO (1500)')
    
    # Add value labels on bars
    for bar, elo in zip(bars, elo_values):
        plt.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 5,
                f'{elo:.0f}', ha='center', va='bottom', fontweight='bold')
    
    plt.xticks(rotation=45, ha='right')
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(vis_dir / f"elo_ratings_{timestamp}.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 4. Victory Points Distribution
    plt.figure(figsize=(14, 8))
    vp_data = []
    for game in enhanced_games:
        for player, vp in game["final_vp_scores"].items():
            vp_data.append({"Player": player, "Victory_Points": vp})
    
    if vp_data:
        vp_df = pd.DataFrame(vp_data)
        sns.boxplot(data=vp_df, x="Player", y="Victory_Points")
        plt.title('Victory Points Distribution by Player', fontsize=16, fontweight='bold')
        plt.xlabel('Player', fontsize=12)
        plt.ylabel('Victory Points', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.savefig(vis_dir / f"vp_distribution_{timestamp}.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    # 5. Combined Performance Dashboard
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('LLM Catan Tournament Performance Dashboard', fontsize=18, fontweight='bold')
    
    # Win rates subplot
    ax1.bar(players, win_rates, color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
    ax1.set_title('Win Rates', fontweight='bold')
    ax1.set_ylabel('Win Rate (%)')
    ax1.set_ylim(0, 100)
    ax1.tick_params(axis='x', rotation=45)
    
    # ELO ratings subplot
    ax2.bar(players, elo_values, color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
    ax2.set_title('ELO Ratings', fontweight='bold')
    ax2.set_ylabel('ELO Rating')
    ax2.axhline(y=1500, color='red', linestyle='--', alpha=0.7)
    ax2.tick_params(axis='x', rotation=45)
    
    # Head-to-head heatmap subplot
    sns.heatmap(h2h_matrix, annot=True, fmt='.0f', cmap='Blues',
                xticklabels=matrix_players, yticklabels=matrix_players,
                ax=ax3, cbar=False)
    ax3.set_title('Head-to-Head Wins', fontweight='bold')
    ax3.tick_params(axis='x', rotation=45)
    
    # Games played and performance
    total_games = [player_stats[player]["games_played"] for player in players]
    wins = [player_stats[player]["wins"] for player in players]
    ax4.bar(players, total_games, alpha=0.6, label='Games Played', color='lightgray')
    ax4.bar(players, wins, alpha=0.8, label='Wins', color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
    ax4.set_title('Games Played vs Wins', fontweight='bold')
    ax4.set_ylabel('Count')
    ax4.legend()
    ax4.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig(vis_dir / f"performance_dashboard_{timestamp}.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    return vis_dir


def calculate_elo_ratings(results):
    """Calculate ELO-style ratings based on head-to-head results."""
    # Initial ratings
    ratings = {
        "GPT-5": 1500,
        "Claude-Sonnet-4": 1500, 
        "Gemini-2.5-Pro": 1500,
        "Kimi-K2": 1500
    }
    
    K = 32  # ELO K-factor
    
    for game in results["games"]:
        winner_info = game.get("winner")
        if not winner_info:
            continue
            
        winner_name = winner_info.get("name")
        is_tie = winner_info.get("is_tie", False)
        players = [p["name"] for p in game["players"]]
        
        # Update ratings for all player pairs
        for i, player1 in enumerate(players):
            for j, player2 in enumerate(players):
                if i != j:
                    # Expected score
                    expected = 1 / (1 + 10**((ratings[player2] - ratings[player1]) / 400))
                    
                    # Actual score based on game outcome
                    if is_tie and isinstance(winner_name, list) and player1 in winner_name:
                        # Tie - partial score
                        actual = 0.5
                    elif not is_tie and player1 == winner_name:
                        # Win
                        actual = 1
                    else:
                        # Loss
                        actual = 0
                    
                    # Update rating
                    ratings[player1] += K * (actual - expected)
    
    return ratings


def calculate_competence_score(player_stats, final_scores_data):
    """
    Calculate overall competence score based on:
    - Win rate (40%)
    - Average final position (30%) 
    - Average victory points (30%)
    """
    competence_scores = {}
    
    for player, stats in player_stats.items():
        if stats["games_played"] == 0:
            competence_scores[player] = 0
            continue
            
        # Win rate component (40%)
        win_rate_score = stats["win_rate"] * 0.4
        
        # Average position component (30%) - lower position is better
        player_positions = []
        player_vps = []
        
        for game_scores in final_scores_data:
            if player in game_scores:
                # Sort by VP descending to get positions
                sorted_players = sorted(game_scores.items(), key=lambda x: x[1], reverse=True)
                position = next(i for i, (p, _) in enumerate(sorted_players, 1) if p == player)
                player_positions.append(position)
                player_vps.append(game_scores[player])
        
        avg_position = sum(player_positions) / len(player_positions) if player_positions else 4
        avg_vp = sum(player_vps) / len(player_vps) if player_vps else 0
        
        # Convert position to score (1st=1.0, 2nd=0.67, 3rd=0.33, 4th=0.0)
        position_score = max(0, (5 - avg_position) / 4) * 0.3
        
        # VP score component (30%) - normalize to 0-1 scale
        vp_score = min(1.0, avg_vp / 10.0) * 0.3
        
        competence_scores[player] = win_rate_score + position_score + vp_score
    
    return competence_scores


def main():
    """Run the competition tournament."""
    print("=== LLM Catan Competition Tournament ===\n")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check API keys
    required_keys = [
        ("OPENAI_API_KEY", "GPT-5"),
        ("ANTHROPIC_API_KEY", "Claude Sonnet 4"), 
        ("GOOGLE_API_KEY", "Gemini 2.5 Pro"),
        ("OPENROUTER_API_KEY", "Kimi K2")
    ]
    
    missing_keys = []
    for env_key, model_name in required_keys:
        if not os.getenv(env_key):
            missing_keys.append(f"{model_name} ({env_key})")
    
    if missing_keys:
        print(f"❌ Missing API keys for: {', '.join(missing_keys)}")
        print("Please set up your .env file with all required API keys.")
        return
    
    print("✅ All API keys found")
    
    # Create tournament manager
    tournament = TournamentManager(
        name="LLM Catan Competition",
        output_dir="tournament_results"
    )
    
    # Add players
    try:
        print("Setting up players...")
        
        gpt5 = GPT5Client()
        tournament.add_player("GPT-5", gpt5)
        print("✅ GPT-5 ready")
        
        claude = ClaudeSonnet4Client() 
        tournament.add_player("Claude-Sonnet-4", claude)
        print("✅ Claude Sonnet 4 ready")
        
        gemini = Gemini25ProClient()
        tournament.add_player("Gemini-2.5-Pro", gemini)
        print("✅ Gemini 2.5 Pro ready")
        
        kimi = KimiK2Client()
        tournament.add_player("Kimi-K2", kimi)
        print("✅ Kimi K2 (via OpenRouter) ready")
        
    except Exception as e:
        print(f"❌ Error setting up players: {e}")
        return
    
    print(f"\n🎮 Starting tournament with 4 LLM players")
    print("Configuration:")
    print("- Tournament format: Round-robin with 3 games per matchup")
    print("- Total games: 3 (1 matchups × 3 games each)")
    print("- Turn limit: 30 rounds (120 turns) or first to 10 VP")
    print("- Standard Catan rules")
    
    # Confirm before running
    response = input("\nProceed with tournament? (y/N): ")
    if response.lower() != 'y':
        print("Tournament cancelled.")
        return
    
    # Run 1 tournament with 3 games per matchup
    print(f"\n🏁 Running Tournament with 3 games per matchup...")
    
    try:
        results = tournament.run_tournament(
            games_per_matchup=3,  # 3 games per matchup for better statistics
            tournament_format="round_robin",
            save_games=True
        )
        
        # Collect final scores from all games
        all_final_scores = []
        for game in results["games"]:
            if "detailed_stats" in game and "final_scores" in game["detailed_stats"]:
                # Map colors to player names
                color_to_player = {p["color"]: p["name"] for p in game["players"]}
                player_scores = {color_to_player[color]: score 
                               for color, score in game["detailed_stats"]["final_scores"].items()
                               if color in color_to_player}
                all_final_scores.append(player_scores)
        
        print(f"✅ Tournament completed with {len(results['games'])} total games")
        
        # Show game results summary
        wins_by_player = {}
        for game in results["games"]:
            if game.get("winner"):
                print(game)
                winner_name = game['winner']['name']
                if isinstance(winner_name, list):
                    for winner in winner_name:
                        wins_by_player[winner] = wins_by_player.get(winner, 0) + 1
                else:
                    wins_by_player[winner_name] = wins_by_player.get(winner_name, 0) + 1
                print(f"   Game winner: {winner_name}")
        
        print(f"\n🏆 Win Summary:")
        for player, wins in wins_by_player.items():
            print(f"   {player}: {wins} wins")
                    
    except Exception as e:
        print(f"❌ Tournament failed: {e}")
        return
    
    # Calculate comprehensive statistics from the single tournament
    print("\n📊 Calculating final rankings...")
    
    # Calculate comprehensive statistics
    player_stats = {}
    for player in ["GPT-5", "Claude-Sonnet-4", "Gemini-2.5-Pro", "Kimi-K2"]:
        player_stats[player] = {
            "games_played": 0,
            "wins": 0,
            "win_rate": 0.0
        }
    
    for game in results["games"]:
        for player_info in game["players"]:
            name = player_info["name"]
            if name in player_stats:
                player_stats[name]["games_played"] += 1
                
                if game.get("winner") and (
                    (isinstance(game["winner"]["name"], list) and name in game["winner"]["name"]) or
                    game["winner"]["name"] == name
                ):
                    player_stats[name]["wins"] += 1
    
    # Calculate win rates
    for name, stats in player_stats.items():
        if stats["games_played"] > 0:
            stats["win_rate"] = stats["wins"] / stats["games_played"]
    
    # Calculate ELO ratings
    elo_ratings = calculate_elo_ratings(results)
    
    # Calculate competence scores
    competence_scores = calculate_competence_score(player_stats, all_final_scores)
    
    # Create final rankings
    print("\n🏆 FINAL RANKINGS")
    print("=" * 80)
    
    # Sort by competence score
    ranked_players = sorted(competence_scores.items(), key=lambda x: x[1], reverse=True)
    
    for i, (player, competence) in enumerate(ranked_players, 1):
        stats = player_stats[player]
        elo = elo_ratings[player]
        
        print(f"{i}. {player}")
        print(f"   Win Rate: {stats['win_rate']:.1%} ({stats['wins']}/{stats['games_played']} wins)")
        print(f"   ELO Rating: {elo:.0f}")
        print(f"   Competence Score: {competence:.3f}")
        print()
    
    # Save detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save summary CSV
    summary_data = []
    for player, competence in ranked_players:
        stats = player_stats[player]
        summary_data.append({
            "Player": player,
            "Games_Played": stats["games_played"],
            "Wins": stats["wins"],
            "Win_Rate": stats["win_rate"],
            "ELO_Rating": elo_ratings[player],
            "Competence_Score": competence
        })
    
    df = pd.DataFrame(summary_data)
    summary_file = f"tournament_results/competition_summary_{timestamp}.csv"
    df.to_csv(summary_file, index=False)
    
    # Create tournament visualizations
    print(f"\n📊 Creating tournament visualizations...")
    try:
        vis_dir = create_tournament_visualizations(results, player_stats, elo_ratings, timestamp)
        print(f"   - Visualizations saved in: {vis_dir}")
    except Exception as e:
        print(f"   - Warning: Failed to create visualizations: {e}")
    
    print(f"\n📁 Results saved:")
    print(f"   - {summary_file}")
    print(f"   - tournament_results/tournament.log")
    
    print(f"\n🎉 Competition tournament completed!")
    print(f"Winner: {ranked_players[0][0]} with {competence_scores[ranked_players[0][0]]:.3f} competence score")


if __name__ == "__main__":
    main()