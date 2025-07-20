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

3. **Run a Simple Game**:
   ```python
   from catanbench.tournament.manager import TournamentManager
   from catanbench.llm_clients.openai_client import OpenAIClient
   from catanbench.llm_clients.claude_client import ClaudeClient
   
   # Create tournament with GPT-4 vs Claude
   tournament = TournamentManager()
   tournament.add_player("GPT-4", OpenAIClient("gpt-4"))
   tournament.add_player("Claude", ClaudeClient("claude-3-sonnet"))
   tournament.run_tournament(games_per_matchup=5)
   ```

## Architecture

```
catanbench/
├── core/              # Core LLM player implementation
├── llm_clients/       # LLM API integrations
├── prompts/           # Prompt engineering system
├── tournament/        # Tournament management
├── utils/             # Utilities and analysis tools
└── config/            # Configuration management
```

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