# SenseMaker Feedback Application

A feedback collection and analysis system inspired by Dave Snowden's SenseMaker methodology from Cognitive Edge. The application allows users to share narrative stories about their experiences and uses LLM-powered analysis with graph database technology to discover emergent patterns.

## Overview

Unlike traditional feedback mechanisms (surveys, ticket systems, Likert scales), this approach:
- Avoids framing bias by letting users tell stories in their own words
- Uses signification rather than categorization (users place stories on continuums, not in boxes)
- Discovers patterns through analysis rather than imposing predetermined categories
- Reveals weak signals and hidden connections across narratives

## Architecture

- **Backend**: FastAPI (Python 3.11+)
- **Databases**:
  - MongoDB (raw story storage)
  - Neo4j (knowledge graph)
  - Redis (caching)
- **LLM Integration**: Abstracted provider interface (Claude, OpenAI, local models)
- **Development**: Docker Compose for local development

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Anthropic API key (for LLM features)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd feedback
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 2. Start Services

```bash
docker-compose up -d
```

This will start:
- MongoDB on port 27017
- Neo4j on ports 7474 (HTTP) and 7687 (Bolt)
- Redis on port 6379
- FastAPI application on port 8000

### 3. Verify Health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### 4. Access Services

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474 (user: neo4j, password: password)

## Development Setup

### Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Code Quality

```bash
# Linting
ruff check .

# Type checking
mypy src/
```

## Project Structure

```
feedback/
├── src/
│   ├── domain/        # Domain models, value objects
│   ├── ports/         # Interface definitions (StoragePort, LLMPort, etc)
│   ├── adapters/      # Infrastructure implementations
│   ├── services/      # Application services
│   └── api/          # FastAPI routes and schemas
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fakes/        # Test implementations of ports
├── config/           # Configuration files
├── docs/             # Project documentation
├── scripts/          # Utility scripts
├── temp/             # Working notes (git-ignored)
└── .beads/           # Issue tracking (bd/beads)
```

## Development Workflow

This project uses:
- **Canon TDD** (Kent Beck's Test-Driven Development)
- **Ports and Adapters** architecture (Hexagonal)
- **Beads (bd)** for issue tracking

See [CLAUDE.md](CLAUDE.md) for detailed development guidelines.
See [AGENTS.md](AGENTS.md) for AI agent workflow instructions.

### Working on Issues

```bash
# Check what's ready to work on
bd ready

# Start working on an issue
bd update feedback-5pi --status in_progress

# Create working directory
mkdir -p temp/feedback-5pi

# Make changes, run tests, commit
git add .
git commit -m "RED: Add test for story submission (feedback-5pi)"

# Complete issue
bd close feedback-5pi
```

## Documentation

- [Project Specification](sensemaker-feedback-project.md) - Full project description and user stories
- [Development Guidelines](CLAUDE.md) - TDD workflow, commit discipline, CRC cards
- [Agent Instructions](AGENTS.md) - AI agent workflow with bd/beads

## License

[To be determined]
