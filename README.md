# CatanBench: LLM Catan Benchmark

A comprehensive benchmark system for evaluating Large Language Models (LLMs) playing Settlers of Catan using the [Catanatron](https://github.com/bcollazo/catanatron) simulator.

## Features

- **Multi-LLM Support**: Test OpenAI GPT, Claude, Gemini, and custom models
- **Full Catan Implementation**: All standard game mechanics including trading, development cards, and special rules
- **Tournament System**: Run comprehensive competitions between different LLMs
- **Strategic Analysis**: Detailed performance metrics and decision quality assessment
- **JSON-based Decision Making**: Structured prompts and responses for reliable parsing

## Quick Start

1. **Setup Environment**:
   ```bash
   python3 -m venv catanbench_env
   source catanbench_env/bin/activate  # On Windows: catanbench_env\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure API Keys**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run the Competition Tournament**:
   ```bash
   python competition_tournament.py
   ```

## Codebase Architecture & Navigation

### 📁 **Core Components**

#### `core/` - Main LLM Player Implementation
- **`llm_player.py`** - The main `LLMPlayer` class that integrates LLMs with Catanatron
  - Handles decision-making loop: game state → prompt → LLM → action
  - Includes retry logic, error handling, and performance tracking
  - Main entry point: `decide(game, playable_actions)` method

- **`game_state.py`** - Game state extraction and serialization
  - `GameStateExtractor` class converts complex Catan state to LLM-friendly JSON
  - Extracts: player resources, board tiles, buildings, strategic context
  - Key method: `extract_state(game, current_player_color)`

- **`action_parser.py`** - Action descriptions and parsing
  - `ActionParser` class converts Catanatron actions to human-readable text
  - Handles all action types: building, trading, development cards, etc.
  - Key method: `describe_actions(actions)` returns indexed action descriptions

#### `models.py` - Unified LLM Clients
- Concrete clients for OpenAI, Anthropic, Google, and OpenRouter
- Shared `BaseLLMClient` interface and `LLMClientError`
- Backwards-compatible aliases: `OpenAIClient`, `ClaudeClient`, `GeminiClient`

#### `prompts/` - Strategic Knowledge & Prompt Engineering
- **`system_prompts.py`** - Core Catan strategy knowledge and rules
  - Expert-level strategic advice for early/mid/late game phases
  - Trading strategies, robber tactics, development card usage
  - Key function: `get_system_prompt()` returns comprehensive Catan expertise

- **`action_templates.py`** - Decision-making templates and examples
  - Structured templates for different decision scenarios
  - Few-shot examples showing optimal play patterns
  - Phase-specific guidance (building, trading, endgame)

#### `tournament/` - Tournament Management
- **`manager.py`** - Main tournament orchestration
  - `TournamentManager` class handles multi-game competitions
  - Round-robin tournaments, result tracking, statistical analysis
  - Key method: `run_tournament(games_per_matchup, format)`

#### `utils/` - Utilities
- **`logging.py`** - Tournament and game logging setup
- Additional analysis and helper functions

### 🎯 **Key Entry Points**

1. **Competition Tournament**: `competition_tournament.py`
2. **Core LLM Player**: `core/llm_player.py` → `LLMPlayer` class
3. **Tournament Management**: `tournament/manager.py` → `TournamentManager` class

### 🔄 **How It All Works Together**

```
1. TournamentManager creates LLMPlayer instances
2. LLMPlayer uses GameStateExtractor to understand game state
3. LLMPlayer uses system prompts + action templates to query LLM
4. LLM response parsed by ActionParser back to Catanatron action
5. Tournament tracks results, performance, and generates reports
```

### 🛠️ **Extending the System**

- **Add new LLM**: Create a new client class in `models.py` inheriting from `BaseLLMClient`
- **Improve strategy**: Modify prompts in `prompts/system_prompts.py`
- **New tournament format**: Extend `TournamentManager` class
- **Custom analysis**: Add utilities to `utils/` directory

### 📊 **Output Files** 
Results are saved in `tournament_results/` (git-ignored by default):
- `tournament_results_*.json` - Complete game data
- `tournament_summary_*.csv` - Game summary for analysis  
- `tournament.log` - Execution logs

### 🧪 **Testing Strategy**
- Mock LLM clients for development (`test_benchmark.py`)
- Real API integration tests (with cost controls)
- Comprehensive error handling and fallback testing

## Supported LLMs

- OpenAI GPT (3.5, 4, 4-turbo)
- Anthropic Claude (3 Haiku, Sonnet, Opus)
- Google Gemini (Pro, Ultra)
- Custom models via API endpoints

## Game Features

- ✅ Settlement and city building
- ✅ Road construction  
- ✅ Resource trading (maritime and player-to-player)
- ✅ Development cards (Knight, Year of Plenty, etc.)
- ✅ Robber movement and resource stealing
- ✅ Victory point tracking
- ✅ All standard Catan rules and mechanics

## License

This project builds upon the GPL-3.0 licensed Catanatron library.