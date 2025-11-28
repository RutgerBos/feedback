# Story Template and Example

## Template for Story Files

```markdown
# Story X.Y: [Title]

**Phase**: [Phase Number and Name]
**Status**: Not Started | In Progress | Blocked | Complete

## User Story

**As a** [role]  
**I want to** [goal]  
**So that** [benefit]

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Technical Tasks

- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

## Definition of Done

- Specific conditions that must be met
- All acceptance criteria checked
- Tests passing

## Notes

- Design decisions made during implementation
- Blockers encountered and resolved
- Links to related stories

## Commits

- [abc123f] Initial implementation
- [def456g] Refactoring

---
**Story completed on**: [Date]
```

## Example: Story 0.1

```markdown
# Story 0.1: Initialize Project Structure

**Phase**: Phase 0 - Project Bootstrap
**Status**: Not Started

## User Story

**As a** developer  
**I want to** have a working project skeleton with all infrastructure configured  
**So that** I can start implementing features immediately

## Acceptance Criteria

- [ ] Git repository initialized with .gitignore
- [ ] Python project structure created (src/, tests/, temp/)
- [ ] pyproject.toml with initial dependencies
- [ ] Docker Compose file with MongoDB, Neo4j, Redis services
- [ ] Environment configuration template (.env.example)
- [ ] README.md with setup and run instructions
- [ ] All services start successfully with docker-compose up
- [ ] Basic health check endpoint returns 200
- [ ] User stories migrated to stories/ directory

## Technical Tasks

- [ ] Initialize git repository
- [ ] Create .gitignore (include temp/, .env, __pycache__, etc.)
- [ ] Create stories/ directory structure
- [ ] Migrate all user stories from project.md to individual story files
- [ ] Create directory structure:
  ```
  sensemaker-feedback/
    src/
      domain/        # Domain models, value objects
      ports/         # Interface definitions
      adapters/      # Infrastructure implementations
      services/      # Application services
      api/          # FastAPI routes and schemas
    tests/
      unit/
      integration/
      fakes/        # Test implementations of ports
    stories/        # User stories (git-tracked)
      phase-0-bootstrap/
      phase-1-capture/
      ...
    temp/           # Working notes (git-ignored)
    docs/           # Project documentation
    config/         # Configuration files
    scripts/        # Utility scripts
  ```
- [ ] Create pyproject.toml with dependencies:
  - FastAPI, uvicorn
  - pymongo, neo4j, redis
  - pytest, pytest-asyncio
  - pydantic
  - anthropic, openai (for LLM providers)
  - pyyaml (for config)
- [ ] Create docker-compose.yml with:
  - MongoDB (with test database)
  - Neo4j Community Edition  
  - Redis
  - FastAPI service (development mode with hot reload)
- [ ] Create .env.example with all configuration variables
- [ ] Write README.md with:
  - Project overview
  - Prerequisites (Docker, Python 3.11+)
  - Setup instructions
  - How to run tests
  - How to access services
- [ ] Create basic FastAPI app (src/api/main.py)
- [ ] Add health check endpoint: GET /health
- [ ] Verify all services can connect
- [ ] First commit: "Initial project structure"

## Definition of Done

- New developer can clone repo and run `docker-compose up`
- All services (MongoDB, Neo4j, Redis, FastAPI) start without errors
- Health check endpoint accessible at http://localhost:8000/health
- Tests can be run with `pytest` (even if no tests exist yet)
- README is clear and complete
- All user stories migrated to stories/ directory
- Git history is clean with good initial commit

## Notes

*Add notes here during implementation*

## Commits

*Add commit hashes and messages here as work progresses*

---
**Story completed on**: [Date when all criteria checked]
```

## stories/README.md Example

```markdown
# User Stories Index

## Progress Overview

- Phase 0: 0/3 complete
- Phase 1: 0/3 complete
- Phase 2: 0/4 complete
- Phase 3: 0/4 complete
- Phase 4: 0/8 complete
- Phase 5: 0/2 complete
- Phase 6: 0/4 complete

**Total**: 0/28 stories complete

## Story Status Legend

- 🔴 Not Started
- 🟡 In Progress
- 🔵 Blocked
- 🟢 Complete

## Phase 0: Project Bootstrap

- 🔴 [Story 0.1](phase-0-bootstrap/story-0.1-project-init.md) - Initialize Project Structure
- 🔴 [Story 0.2](phase-0-bootstrap/story-0.2-triad-config.md) - Configure Triad Definitions
- 🔴 [Story 0.3](phase-0-bootstrap/story-0.3-core-ports.md) - Define Core Port Interfaces

## Phase 1: Core Data Capture

- 🔴 [Story 1.1](phase-1-capture/story-1.1-submit-story.md) - Submit Story with Triad Placement
- 🔴 [Story 1.2](phase-1-capture/story-1.2-metadata.md) - Include Optional Metadata
- 🔴 [Story 1.3](phase-1-capture/story-1.3-view-stories.md) - View Raw Story Data

## Phase 2: LLM Processing Pipeline

- 🔴 [Story 2.1](phase-2-llm-processing/story-2.1-llm-abstraction.md) - Abstract LLM Provider Interface
- 🔴 [Story 2.2](phase-2-llm-processing/story-2.2-extract-entities.md) - Extract Entities from Stories
- 🔴 [Story 2.3](phase-2-llm-processing/story-2.3-extract-themes.md) - Extract Themes and Topics
- 🔴 [Story 2.4](phase-2-llm-processing/story-2.4-sentiment.md) - Analyze Sentiment and Emotional Tone

... and so on for all phases

## Updating This Index

When completing a story:
1. Check all acceptance criteria in the story file
2. Add completion date to story file
3. Update this index to show 🟢
4. Update progress counts at top

When starting a story:
1. Update status to 🟡 in this index
2. Update Status field in story file to "In Progress"
3. Create temp/story-X.Y-name/ directory for working notes
```

## Usage in Development

1. **Before starting work**: Read the story file, create temp directory
2. **During work**: Update story file with notes, commits
3. **When complete**: Check all boxes, add completion date
4. **Reference in commits**: "Implements story-1.1: Submit story with triad placement"
5. **Track progress**: Update stories/README.md index

## Benefits

- Git-native (no external tools required)
- Each story is independently versionable
- Can track progress with simple checkboxes
- Easy to reference in commits and documentation
- Works offline
- Simple text files, easy to read and edit
- Maps to temp/story-X.Y/ working directory structure
