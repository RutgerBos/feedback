# AI Agent Instructions for SenseMaker Feedback Application

This is the canonical instruction file for this repository. `CLAUDE.md` is a symlink to this file, kept for tools that look for that name specifically — edit only this file.

## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Auto-syncs to JSONL for version control
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**
```bash
bd ready --json
```

**Create new issues:**
```bash
bd create "Issue title" -t bug|feature|task -p 0-4 --json
bd create "Issue title" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**
```bash
bd update bd-42 --status in_progress --json
bd update bd-42 --priority 1 --json
```

**Complete work:**
```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task**: `bd update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`
6. **Commit together**: Always commit the `.beads/issues.jsonl` file together with the code changes so issue state stays in sync with code state

### Auto-Sync

bd automatically syncs with git:
- Exports to `.beads/issues.jsonl` after changes (5s debounce)
- Imports from JSONL when newer (e.g., after `git pull`)
- No manual export/import needed!

## Git Workflow

**Branch Strategy**: Each user story is developed on its own feature branch.

### Starting a New Story

1. **Create a feature branch** from main:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b story-X.Y-short-description
   # Example: git checkout -b story-1.1-submit-story
   ```

2. **Work on the story** following TDD:
   - Make commits as you progress (RED, GREEN, REFACTOR)
   - Reference the beads issue in commit messages (e.g., `feedback-abc`)
   - Keep commits focused and atomic

3. **Create a Pull Request** when story is complete:
   ```bash
   # Push the branch
   git push -u origin story-X.Y-short-description

   # Create PR using GitHub CLI
   gh pr create --title "Story X.Y: Description" --body "$(cat <<'EOF'
   ## Summary
   <Brief description of what was implemented>

   ## Changes
   - Change 1
   - Change 2

   ## Tests
   All X tests passing

   ## Beads Issue
   Closes feedback-xyz

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   EOF
   )"
   ```

4. **After PR is merged**:
   - Close the beads issue: `bd close feedback-xyz`
   - Delete the local branch: `git branch -d story-X.Y-short-description`
   - Pull latest main: `git checkout main && git pull origin main`

### Benefits of This Workflow

- **Isolated development**: Each story is self-contained
- **Easy code review**: PR contains all changes for one story
- **Safe experimentation**: Can abandon branch if approach doesn't work
- **Clean history**: Main branch only contains completed, reviewed work
- **Parallel work**: Multiple stories can be developed simultaneously on different branches

## Philosophy

This project follows **Kent Beck's pure Test-Driven Development** methodology and maintains strict separation between behavioral and structural changes. The goal is to build software incrementally, with confidence, through small safe steps.

## Test-Driven Development (Canon TDD)

### The Core Workflow

Follow Kent Beck's Canon TDD exactly as described in his "Canon TDD" article:

1. **Write a Test List** - List all the test scenarios you want to cover for the feature
2. **Turn One Item Into a Test** - Pick exactly one item and write a concrete, runnable test
3. **Make It Pass** - Change the code to make the test (and all previous tests) pass
4. **Optionally Refactor** - Improve the implementation design
5. **Repeat** - Go back to step 2 until the list is empty

### The Red-Green-Refactor Loop

Every few minutes, cycle through these three phases:

**RED**: Write a failing test
- Predict (mentally or out loud) how the test should fail
- Run the test and see it fail
- If it fails in an unexpected way, check your assumptions
- Improve the failure's readability

**GREEN**: Make the test pass ASAP
- Commit any sins necessary
- Use hard-coded values if needed
- Use if statements
- Fake it until you make it
- **Do NOT refactor yet** - make it run first, then make it right

**REFACTOR**: Improve the design without changing behavior
- Atone for your sins
- Remove duplication (including between test and implementation)
- Improve names
- Make it look as if you knew all along what you were doing

### Critical Rules and Common Mistakes

**DO:**
- Keep a TODO list of tests as you discover new cases
- Write tests with setup, invocation, AND assertions (try working backwards from assertions)
- Make the smallest possible test pass
- Add new test cases to your list as you discover them during implementation
- Start over with a different test order if a new test invalidates previous work
- Call your shot before running tests: "Is this one gonna pass?"
- Use "Fake it till you make it" - return constants first, then gradually generalize
- Write tests that tell little stories (good test names)

**DON'T:**
- Mix refactoring into making the test pass (wear one hat at a time)
- Convert all test list items into concrete tests before making any pass
- Copy actual computed values and paste them into expected values (defeats double-checking)
- Write tests without assertions just for code coverage
- Mix implementation design decisions into the test list (that comes later)
- Write more production code than necessary to pass the current test

### Test List Management

**Starting a new feature:**
```
TODO List for Story 1.1 - Submit Story with Triad Placement:
[ ] Can submit story with valid text and triad coordinates
[ ] Validates minimum story length (50 chars)
[ ] Validates maximum story length (2000 chars)
[ ] Requires all triad placements before submission
[ ] Generates UUID for new story
[ ] Stores timestamp with story
[ ] Returns story ID on successful submission
[ ] Shows confirmation message to user
```

As you work, add new items as you discover them:
```
TODO List for Story 1.1:
[x] Can submit story with valid text and triad coordinates
[ ] Validates minimum story length (50 chars)
[ ] What if coordinates are out of bounds? <- discovered during implementation
[ ] Validates maximum story length (2000 chars)
...
```

### Two Kinds of Design

**Interface Design** (decided during test writing):
- How is the behavior invoked?
- What does the API look like?
- What are the method signatures?

**Implementation Design** (decided during refactoring):
- How does the system implement the behavior?
- What's the internal structure?
- What are the private methods and classes?

**Never mix these two** - you'll make interface decisions while writing tests, and implementation decisions while refactoring.

## Behavioral vs Structural Changes

Following Kent Beck's "two hats" principle: **Always be making one kind of change or the other, but never both at the same time.**

### Behavioral Changes (B∆)

Changes that alter what the program does:
- Adding new features
- Fixing bugs
- Changing business logic
- Modifying API responses
- Adding new endpoints
- Changing validation rules

**Behavioral commits:**
- Must have passing tests that demonstrate the new/changed behavior
- Should be reviewable for correctness and side effects
- Tests are PART of the behavioral change

### Structural Changes (S∆)

Changes that alter how the code is organized without changing what it does:
- Extracting methods or classes
- Renaming variables, methods, classes
- Moving code between files
- Removing duplication
- Improving names
- Reordering code
- Inlining methods
- Changing internal data structures (if behavior unchanged)

**Structural commits:**
- Must pass ALL existing tests unchanged
- Should be reviewable for contribution toward better structure
- Are reversible (you can always undo them)
- Can be made more lightly than behavioral changes

### Commit Discipline

**Split your commits religiously:**

**BAD - Mixed commit:**
```
commit: Add user authentication and refactor database layer
- Added login endpoint
- Extracted database connection to helper
- Renamed variables for clarity
- Fixed password validation
```

**GOOD - Separated commits:**
```
commit 1 (Structural): Extract database connection to helper
commit 2 (Structural): Rename database variables for clarity
commit 3 (Behavioral): Add login endpoint with password validation
```

### The "Tidy First" Workflow

When facing messy code that needs a behavioral change:

1. **Tidy First** - Make structural changes to clean up the code
2. **Commit** (structural commit)
3. **Add Behavior** - Make the behavioral change (now easier)
4. **Commit** (behavioral commit)
5. **Tidy After** - Clean up any mess made during behavioral change
6. **Commit** (structural commit)

**Alternative: "Tidy Later"**
- Sometimes you should make the behavioral change first
- Then tidy afterward when you see a better structure
- Still keep commits separate

### When to Refactor

**During TDD:**
- ONLY during the Refactor step of Red-Green-Refactor
- After tests are green
- Before writing the next test

**When NOT to refactor:**
- While trying to make a test pass (stay in GREEN phase)
- Code you're not currently changing
- Just because it's "not perfect" - refactor to make the next change easier

### Using Git for TDD

**Workflow:**
```bash
# Start with a test
git add test_story_submission.py
git commit -m "RED: Add test for story submission"

# Make it pass (even with sins)
git add -A
git commit -m "GREEN: Make story submission test pass (hardcoded)"

# Refactor
git add -A
git commit -m "REFACTOR: Extract story validation logic"

# Every commit keeps tests passing (except RED commits which are expected to have failing tests)
```

**Advanced: Separate behavioral and structural changes**

If you accidentally mixed changes:
```bash
# Use interactive rebase to split
git rebase -i HEAD~3

# Or use git add -p to stage selectively
git add -p file.py  # Select only structural changes
git commit -m "REFACTOR: Rename variables"
git add -A
git commit -m "FEAT: Add new validation"
```

## Progress Tracking

Use a `./temp/` directory (git-ignored) for working notes on bd issues.

### Directory Structure

```
temp/
  feedback-5pi/
    progress.md          # Test list with checkmarks, discoveries
    notes.md             # Design decisions, questions, blockers
    scratch.py           # Experimental code snippets
  feedback-abc/
    progress.md
    notes.md
  feedback-def/
    progress.md
    notes.md
    spike-providers.py
```

**Note**: Directory names use bd issue IDs (e.g., `feedback-5pi`). This makes it easy to cross-reference between code, notes, and `bd show <id>`.

### progress.md Template

```markdown
# feedback-5pi: Submit Story with Triad Placement

**bd issue**: feedback-5pi
**Status**: In Progress

## Test List
- [x] Can submit valid story (basic happy path)
- [x] Story ID is generated and returned
- [ ] Validates minimum length (50 chars)
  - Note: Need to decide on error message format
- [ ] Requires all three triad coordinates
  - Discovered: Need to handle out-of-bounds coordinates

## Commits
- abc123f RED: Add test for story submission (feedback-5pi)
- def456g GREEN: Make story submission pass
- ghi789h REFACTOR: Extract validation logic
- jkl012m RED: Add test for minimum length validation

## Design Decisions
- Using Pydantic for request validation
- Storing coordinates as {x, y} dict in barycentric space
- MongoDB document structure: story_id as _id field

## Blockers
None currently

## Questions
- Should we validate coordinate bounds here or in frontend?
- What HTTP status for validation failures? (Decision: 400)

## Next Session
Start with minimum length validation test, then max length
```

### notes.md Format

Use for more detailed exploration:

```markdown
# Notes: feedback-5pi

## 2024-11-28 - Initial Implementation

Discovered that barycentric coordinates need normalization. The three
coordinates (x, y, z) should sum to 1.0. Frontend handles this, but
should we validate server-side too?

Decided: Yes, add validation. Defense in depth.

## 2024-11-28 - Refactoring Session

Extracted CoordinateValidator class. Initially tried to make it a pure
function but realized we might want to make tolerance configurable later.
Class gives us that flexibility.

See commit: ghi789h

## Interface Design Decision

API endpoint: POST /api/stories
Request body:
{
  "story_text": "...",
  "triads": [
    {"triad_id": "workflow", "coordinates": {"x": 0.3, "y": 0.6}}
  ],
  "metadata": {...}  // optional
}

Response: {"story_id": "uuid", "timestamp": "iso8601"}
```

### Benefits

- **Survives sessions** - Come back next day and know exactly where you left off
- **Context preservation** - Design decisions stay linked to the story
- **Git-clean** - No WIP noise in project history
- **Debugging aid** - Track what you tried and why
- **Handoff ready** - Another developer (or you in 6 months) can pick up easily

### When to Update

**progress.md:**
- Start of story: Create with initial test list
- After each test: Check off completed tests
- After commits: Log commit hash and message
- End of session: Update "Next Session" section
- When blocked: Document in Blockers section

**notes.md:**
- When making design decisions
- When discovering something important
- When trying different approaches
- When answering questions that came up

### .gitignore Entry

```
# Working notes and scratch files
temp/
*.swp
*.swo
```

## CRC Cards (Class-Responsibility-Collaborator)

Use CRC cards to design and document classes. This helps keep classes focused and reveals when responsibilities are misplaced or collaborations are too complex.

### Card Format

Cards live in class docstrings as an `<crc>`/`</crc>`-delimited YAML block, parsed by `crc_generator`'s Python plugin. The schema is strict: exactly two keys, `responsibilities` and `collaborators`, both string arrays. No `notes`, no rationale, no other keys.

```python
class CoordinateValidator:
    """
    <crc>
    responsibilities:
      - Validate coordinate bounds (0.0 to 1.0)
      - Validate barycentric constraint (sum to 1.0)
    collaborators: []
    </crc>
    """

    def validate(self, coordinates: dict) -> ValidationResult:
        ...
```

With collaborators:

```python
class StorySubmissionService:
    """
    <crc>
    responsibilities:
      - Validate story text length
      - Validate triad coordinates
      - Assign story ID and timestamp
      - Coordinate storage
    collaborators:
      - StoragePort
      - CoordinateValidator
      - Story
    </crc>
    """

    def __init__(self, storage: StoragePort, validator: CoordinateValidator):
        self.storage = storage
        self.validator = validator
```

Rules for the payload:
- Use bare collaborator names, not parenthetical rationale (`StoragePort`, not `StoragePort (to persist story)`).
- Empty collaborators is `collaborators: []`, never `- None` or an omitted key.
- Author conceptual responsibilities and collaborators, not a mechanical dependency inventory — differences between the card and what the analyzer detects are useful drift signals, not necessarily bugs to fix.
- If you have design commentary worth keeping (why a class looks the way it does, a link to the commit that shaped it), put it in ordinary prose in the docstring outside the `<crc>` block, not inside the YAML payload.

**Why in the code:**
- Always up to date (or obviously out of date)
- Colocated with what it describes
- Visible during refactoring
- Can't get lost or forgotten
- Part of the actual artifact

**Temporary sketches during design:**
- Use `temp/<bd-issue-id>/design-sketch.md` for exploring ideas
- Once you commit the class, move the CRC card into the docstring
- Temp should only have "what if we did it this way?" explorations

### When to Write CRC Cards

**During RED phase (writing tests):**
- Sketch the class you wish existed in temp notes
- What responsibilities would make the test clean?
- What collaborators does it need?

**During GREEN phase (implementing):**
- Write the CRC card as the class docstring FIRST
- Then implement to match the card
- If implementation doesn't match, update the card

**During REFACTOR phase:**
- Update CRC cards when extracting classes
- Update cards when responsibilities shift
- Delete cards when inlining/removing classes
- If card and code don't match, that's a smell

**Code review:**
- Read the CRC card first
- Does the implementation match?
- Are responsibilities clear from the code?
- Should the card be updated?

### Signs of Good CRC Cards

✅ **Clear, focused responsibilities**
- Each responsibility is one clear sentence
- Typically 3-5 responsibilities max
- You can explain what it does without "and"

✅ **Appropriate collaborations**
- Collaborates through interfaces (Ports), not concrete classes
- Knows about 3-5 collaborators max
- Dependencies point inward (toward domain)

✅ **Pure classes**
- Domain logic classes have no infrastructure dependencies
- Coordination classes just coordinate, don't contain logic
- Value objects are immutable and self-validating

### Signs of Problems

❌ **Too many responsibilities**
- "...and also..."
- "depending on X, it does Y or Z"
- More than 5-7 responsibilities
- **Solution**: Extract classes

❌ **Too many collaborators**
- More than 5-7 collaborators
- Collaborates with concrete classes instead of interfaces
- **Solution**: Introduce a Facade or extract a service layer

❌ **Confused responsibilities**
- Business logic mixed with infrastructure
- Validation mixed with persistence
- Domain knowledge in service layer
- **Solution**: Separate concerns, move logic to domain

❌ **Circular dependencies**
- Class A needs Class B needs Class A
- **Solution**: Extract interface, or introduce mediator

### Example: Discovering a Problem Through CRC Cards

**BEFORE - problematic class:**

```python
class StoryProcessor:
    """
    <crc>
    responsibilities:
      - Validate story text
      - Validate coordinates
      - Call LLM to extract entities
      - Parse LLM response
      - Save story to MongoDB
      - Create Neo4j nodes
      - Update cache
      - Log errors
      - Send metrics
    collaborators:
      - MongoDBClient
      - Neo4jClient
      - RedisClient
      - LLMClient
      - Logger
      - MetricsCollector
    </crc>
    """
```

**Looking at this card, we immediately see problems:** too many responsibilities, knows about all infrastructure, hard to test without mocking everything. Time to refactor.

**AFTER - refactored into focused classes:**

```python
class StoryProcessor:
    """
    <crc>
    responsibilities:
      - Coordinate story processing workflow
      - Handle processing errors
    collaborators:
      - StoragePort
      - EntityExtractor
      - GraphBuilder
    </crc>
    """

    def __init__(
        self,
        storage: StoragePort,
        extractor: EntityExtractor,
        graph_builder: GraphBuilder
    ):
        self.storage = storage
        self.extractor = extractor
        self.graph_builder = graph_builder

    def process(self, story: Story) -> ProcessingResult:
        story_id = self.storage.save(story)
        entities = self.extractor.extract(story.text)
        self.graph_builder.build(story_id, entities)
        return ProcessingResult(story_id=story_id)


class EntityExtractor:
    """
    <crc>
    responsibilities:
      - Extract entities from story text
      - Map LLM response to domain model
    collaborators:
      - LLMPort
      - Entity
    </crc>
    """

    def __init__(self, llm: LLMPort):
        self.llm = llm

    def extract(self, text: str) -> list[Entity]:
        response = self.llm.extract_entities(text)
        return [Entity.from_dict(e) for e in response["entities"]]


class GraphBuilder:
    """
    <crc>
    responsibilities:
      - Build knowledge graph from extracted data
      - Create nodes and relationships
    collaborators:
      - GraphPort
      - Entity
      - Theme
    </crc>
    """

    def __init__(self, graph: GraphPort):
        self.graph = graph

    def build(self, story_id: str, entities: list[Entity]) -> None:
        story_node = StoryNode(id=story_id)
        self.graph.create_node(story_node)

        for entity in entities:
            entity_node = EntityNode.from_entity(entity)
            self.graph.create_node(entity_node)
            self.graph.create_relationship(story_node, entity_node, "MENTIONS")
```

**The refactoring process:**
1. Saw the problematic CRC card in the docstring
2. Extracted responsibilities into focused classes
3. Wrote CRC cards for new classes
4. Now each class is testable with simple fakes

### Review Questions

Ask these about each CRC card:

1. **Could I explain this class to a 5-year-old?** If not, too complex
2. **Could I swap out any collaborator?** If not, too coupled
3. **Could I test this with fakes, no mocks?** If not, bad boundaries
4. **Is it doing one thing?** If not, extract classes
5. **Would Ward Cunningham nod approvingly?** If not, keep refactoring

CRC cards originated with Ward Cunningham and Kent Beck in the late 1980s as a tool for teaching object-oriented thinking. They're still valuable for keeping designs clean and focused.

### Tooling: crc_generator

- Use the installed `crc-card-authoring` skill when creating, correcting, or reviewing CRC cards.
- During refactoring, run the CRC analyzer before and after the affected change when practical:
  ```bash
  cd ../crc_generator
  core/bin/crc analyze --plugin python --source ../feedback/src
  ```
- Review dangling collaborators, cycles, fan-out, and responsibility outliers as design signals. Do not change a conceptual card solely to silence a diagnostic.
- Before merging CRC-affecting changes, analyze the full `src` tree and verify that any remaining diagnostics are intentional.

## Working with AI Agents

### Starting a New User Story

When beginning work on a bd issue:

1. **Create temp directory** - `mkdir -p temp/<bd-issue-id>`
2. **Read the issue** - `bd show <bd-issue-id>`
3. **Create progress.md** - Use the template above, include the bd issue ID
4. **Create a test list** - List all test scenarios (behavioral analysis)
5. **Share the test list** with the user for review
6. **Pick the first test** - Usually the simplest case
7. **Write the failing test** (RED)
8. **Make it pass** (GREEN) - sins allowed!
9. **Refactor** if needed
10. **Commit** - separate behavioral and structural, reference the issue in commit
11. **Update progress.md** - Check off test, log commit
12. **Repeat** for next test on list

### Example Session

```
User: "Let's start on feedback-5pi - Submit Story with Triad Placement"

Agent: "I'll create the working directory and progress file first..."

[Creates temp/feedback-5pi/progress.md]

Agent: "I've read feedback-5pi. Here's my test list:

TODO - feedback-5pi:
[ ] Can submit valid story (basic happy path)
[ ] Story ID is generated and returned
[ ] Timestamp is recorded
[ ] Coordinates are stored correctly
[ ] Validates minimum length (50 chars)
[ ] Validates maximum length (2000 chars)
[ ] Requires all three triad coordinates
[ ] Returns 400 for invalid input
[ ] MongoDB document structure matches schema

Let's start with the simplest: submitting a valid story.

First, I'll write the test..."

[Agent writes failing test, commits with "RED: Add test for story submission (feedback-5pi)"]
[Agent makes it pass, commits with "GREEN: Make story submission pass (feedback-5pi)"]
[Agent refactors if needed, commits with "REFACTOR: Extract validation (feedback-5pi)"]
[Agent updates progress.md with checkmark and commit hashes]

Agent: "Test passes. Moving to next test: Story ID generation..."
```

### Continuing Across Sessions

```
User: "Let's continue feedback-5pi"

Agent: "Let me check the progress file and the issue..."

[Reads temp/feedback-5pi/progress.md, runs bd show feedback-5pi]

Agent: "I can see we completed the basic submission and ID generation.
The progress file says next session should start with minimum length
validation. There's a note about deciding error message format.

Should we decide on that now, or just pick a format and iterate?"
```

### Commit Message Format

Use prefixes to indicate commit type and always reference the bd issue:

**Behavioral commits:**
- `FEAT: Add story submission endpoint (feedback-abc)` - New feature
- `FIX: Correct coordinate validation logic (feedback-abc)` - Bug fix
- `TEST: Add tests for existing behavior (feedback-abc)` - Adding tests
- `RED: Add test for story submission (feedback-abc)` - TDD red phase
- `GREEN: Make story submission test pass (feedback-abc)` - TDD green phase

**Structural commits:**
- `REFACTOR: Extract coordinate validation (feedback-abc)` - Code restructuring
- `RENAME: Clarify story processor naming (feedback-abc)` - Renaming
- `MOVE: Relocate validators to domain (feedback-abc)` - Moving code
- `EXTRACT: Create CoordinateValidator class (feedback-abc)` - Extracting
- `INLINE: Remove unnecessary abstraction (feedback-abc)` - Inlining

**Other:**
- `DOCS: Update API documentation (feedback-abc)` - Documentation only
- `CHORE: Update dependencies (feedback-abc)` - Build, dependencies, config

**Example Commit History:**

```
REFACTOR: Extract coordinate validation to helper (feedback-abc)
GREEN: Make triad coordinate validation test pass (feedback-abc)
RED: Add test for out-of-bounds coordinates (feedback-abc)
REFACTOR: Rename story_data to story_document (feedback-abc)
GREEN: Make story submission test pass (feedback-abc)
RED: Add test for story submission endpoint (feedback-abc)
FEAT: Add MongoDB connection configuration (feedback-abc)
```

## Code Quality Guidelines

### KISS and YAGNI

- **Keep It Simple, Stupid** - The simplest thing that makes the test pass
- **You Aren't Gonna Need It** - Don't add features until you have a test for them

### Duplication

Duplication between test and implementation is a signal:
```python
# Test
def test_multiply():
    dollar = Dollar(5)
    dollar.times(2)
    assert dollar.amount == 10  # Hard-coded expected value

# Implementation (during GREEN phase)
def times(self, multiplier):
    self.amount = 5 * 2  # Duplication with test!

# After REFACTOR phase
def times(self, multiplier):
    self.amount = self.amount * multiplier  # Duplication removed
```

The duplication tells you the implementation isn't done yet.

### Small Steps

When stuck or when tests are failing unexpectedly:
- Take smaller steps
- Break the test into even simpler tests
- Back up to the last passing state (git is your friend)
- Start with an even simpler case

**Kent Beck's advice**: "I make this kind of decision every single moment when I do TDD"

### Test Isolation

**Tests should leave the world the same way they found it:**
- Clean up database records
- Reset global state
- Independent of execution order
- Can run individually or in any combination

**Use fixtures and teardown:**
```python
@pytest.fixture
def db_connection():
    # Setup
    conn = create_test_database()
    yield conn
    # Teardown
    conn.drop_all_tables()
    conn.close()
```

## Managing AI-Generated Planning Documents

AI assistants often create planning and design documents during development:
- PLAN.md, IMPLEMENTATION.md, ARCHITECTURE.md
- DESIGN.md, CODEBASE_SUMMARY.md, INTEGRATION_PLAN.md
- TESTING_GUIDE.md, TECHNICAL_DESIGN.md, and similar files

**Best Practice: Use a dedicated directory for these ephemeral files**

**Recommended approach:**
- Create a `history/` directory in the project root
- Store ALL AI-generated planning/design docs in `history/`
- Keep the repository root clean and focused on permanent project files
- Only access `history/` when explicitly asked to review past planning

**Example .gitignore entry (optional):**
```
# AI planning documents (ephemeral)
history/
```

**Benefits:**
- ✅ Clean repository root
- ✅ Clear separation between ephemeral and permanent documentation
- ✅ Easy to exclude from version control if desired
- ✅ Preserves planning history for archeological research
- ✅ Reduces noise when browsing the project

## Project-Specific Guidelines

### Technology Stack

- **Backend**: Python with FastAPI
- **Databases**: MongoDB (raw data), Neo4j (graph), Redis (cache)
- **Testing**: pytest
- **LLM**: Abstracted provider interface

### Architecture: Ports and Adapters (Hexagonal)

Use **Ports** (interfaces) to define contracts and **Adapters** to implement them:

**Ports** (domain interfaces):
```python
# ports/storage.py
class StoragePort(ABC):
    @abstractmethod
    def save_story(self, story: Story) -> str:
        pass

    @abstractmethod
    def get_story(self, story_id: str) -> Story:
        pass

# ports/llm.py
class LLMPort(ABC):
    @abstractmethod
    def extract_entities(self, text: str) -> dict:
        pass
```

**Adapters** (infrastructure implementations):
```python
# adapters/mongodb_storage.py
class MongoDBStorageAdapter(StoragePort):
    def save_story(self, story: Story) -> str:
        # MongoDB-specific implementation
        pass

# adapters/claude_llm.py
class ClaudeLLMAdapter(LLMPort):
    def extract_entities(self, text: str) -> dict:
        # Anthropic API implementation
        pass
```

**Test Implementations** (in-memory fakes):
```python
# tests/fakes/storage.py
class InMemoryStorage(StoragePort):
    def __init__(self):
        self.stories = {}

    def save_story(self, story: Story) -> str:
        story_id = str(uuid4())
        self.stories[story_id] = story
        return story_id
```

**Benefits for TDD:**
- Tests use real in-memory implementations, not mocks
- Can test domain logic without databases or external services
- Refactor adapters without touching tests
- Design feedback: if it's hard to create a fake, boundaries are wrong

### Testing Strategy

**Unit Tests:**
- Test individual functions/methods
- Fast, isolated
- No database or external dependencies (use fakes, not mocks)

**Integration Tests:**
- Test API endpoints end-to-end
- Use test database instances
- Verify database state changes

**Example structure:**
```
tests/
  unit/
    test_story_validation.py
    test_coordinate_calculation.py
    test_llm_provider_interface.py
  integration/
    test_story_submission_api.py
    test_mongodb_storage.py
    test_neo4j_graph_construction.py
```

### Test Data

Keep test data minimal and meaningful:
```python
def test_story_submission():
    story_data = {
        "story_text": "I had to restart the CI pipeline three times today.",
        "triads": [
            {"triad_id": "workflow", "coordinates": {"x": 0.3, "y": 0.6}}
        ]
    }
    # Not a wall of JSON
```

### Dependency Injection and Test Implementations

**Instead of mocking, use dependency injection with real test implementations:**

```python
# Design: Define interfaces (Ports)
class LLMPort(ABC):
    @abstractmethod
    def extract_entities(self, story: str) -> dict:
        pass

# Production: Real implementation (Adapter)
class ClaudeLLMProvider(LLMPort):
    def extract_entities(self, story: str) -> dict:
        response = anthropic.messages.create(...)
        return parse_response(response)

# Testing: In-memory fake implementation
class FakeLLMProvider(LLMPort):
    def __init__(self, canned_responses: dict):
        self.responses = canned_responses

    def extract_entities(self, story: str) -> dict:
        return self.responses.get("entities", {"entities": [], "types": []})

# Test: Inject the fake
def test_entity_extraction():
    fake_llm = FakeLLMProvider(canned_responses={
        "entities": {
            "entities": ["CI pipeline", "restart"],
            "types": ["tool", "action"]
        }
    })
    processor = StoryProcessor(llm=fake_llm)

    result = processor.process_story(story)
    assert "CI pipeline" in result.entities
```

**Why this is better than mocking:**
- Tests stay focused on public interfaces, not implementation details
- Can refactor internals without breaking tests
- Fake implementations are reusable across tests
- No knowledge of internal method calls or structure
- Fakes can be tested themselves to ensure they match the interface contract

### When Mocking Might Be Acceptable

Mocking has limited valid use cases. Before reaching for a mock, ask: "Should this be a proper interface with a test implementation instead?"

**Rare acceptable cases:**

1. **Truly external third-party services** you don't control and can't easily fake
   - But even then, prefer wrapping in a thin adapter with an interface
   - Example: Payment processors, SMS gateways

2. **Cross-cutting concerns** like logging or metrics
   - These are side effects you usually don't need to verify
   - If you DO need to verify them, they should be interfaces

3. **Temporarily during exploration**
   - Quick spike to understand something
   - Should be replaced with proper design before committing

**Red flags that mocking is wrong:**

- Mocking multiple dependencies in one test
- Tests that know about internal method call sequences
- Need to mock private methods or attributes
- Mocks that return other mocks
- Tests break when you refactor (but behavior didn't change)

**The design feedback:**

If creating a test implementation feels hard or awkward, listen to that feedback:
- Maybe the interface is too broad (violates Interface Segregation)
- Maybe the class has too many dependencies
- Maybe the boundaries are in the wrong place

TDD should guide you toward better design. Mocking can silence that feedback.

### Database Test Fixtures

For integration tests that actually hit databases, use real test instances:

```python
@pytest.fixture(scope="session")
def mongodb_container():
    """Spin up a real MongoDB container for tests"""
    with MongoDBContainer() as mongo:
        yield mongo.get_connection_url()

@pytest.fixture
def clean_db(mongodb_container):
    """Provide a clean database for each test"""
    client = MongoClient(mongodb_container)
    yield client.test_db
    client.drop_database('test_db')  # Clean up after test

def test_story_storage_integration(clean_db):
    """Integration test with real MongoDB"""
    adapter = MongoDBStorageAdapter(clean_db)
    story = Story(text="Test story", triads=[...])

    story_id = adapter.save_story(story)
    retrieved = adapter.get_story(story_id)

    assert retrieved.text == "Test story"
```

**Why real test databases:**
- Actually test your adapter implementations
- Catch database-specific issues (constraints, transactions, etc.)
- More confidence than mocking database behavior
- Still fast with containers (spin up once per test session)

## Anti-Patterns to Avoid

### Testing Anti-Patterns

❌ **Overusing mocks instead of dependency injection**
- Mocks couple tests to implementation details
- Tests break when you refactor internals
- Sign that boundaries are in the wrong place
- **Instead**: Use interfaces with in-memory fake implementations
- **Exception**: Truly external services you don't control (and even then, prefer a thin adapter)

❌ **Writing tests after the code**
- You lose the design benefit of TDD
- Tests become protection for existing code, not drivers of design

❌ **Making multiple tests pass at once**
- You lose the rhythm of red-green-refactor
- Harder to know what change fixed what

❌ **Tests without assertions**
- Just for code coverage
- Don't actually verify behavior

❌ **Testing implementation details**
- Tests become brittle
- Can't refactor without changing tests
- **Example**: Testing that a specific private method was called
- **Instead**: Test observable behavior through public interfaces

### Commit Anti-Patterns

❌ **Mixing behavioral and structural changes**
- Makes code review harder
- Can't revert structure without reverting behavior
- Loses the "two hats" safety

❌ **Giant refactoring commits**
- Risky, hard to review
- Should be broken into many small structural commits

❌ **"WIP" or "misc changes" commit messages**
- Loses project history
- Can't understand what changed and why

### Tracking Anti-Patterns

❌ **Do NOT create markdown TODO lists** - use bd
❌ **Do NOT use external issue trackers** - bd is the single source of truth
❌ **Do NOT duplicate tracking systems**
❌ **Do NOT clutter repo root with planning documents** - use `history/`

## When Things Go Wrong

### Test Won't Pass

1. **Check your assumptions** - Did it fail the way you expected?
2. **Simplify the test** - Can you make it even simpler?
3. **Take smaller steps** - Maybe you tried to do too much
4. **Revert** - Go back to last green state and try a different approach

### Test Suite Running Slow

1. **Check test isolation** - Are tests truly independent?
2. **Isolate expensive operations** - Database, network calls, LLM calls behind ports
3. **Use test fixtures efficiently** - Session vs function scope
4. **Separate fast unit tests from slow integration tests**

### Can't Figure Out How to Refactor

1. **Let it sit** - Move to next test, patterns may emerge
2. **Duplication is okay temporarily** - Better than wrong abstraction
3. **The rule of three** - Wait until you see something three times before abstracting
4. **Small refactorings** - Extract method, rename variable, move code

### Stuck on Design

1. **Sketch on paper** - Sharpie on napkin is fine
2. **Write the test you wish you had** - Let the test drive the interface
3. **Start with the assertions** - Work backwards
4. **Fake it** - Hard-code the return value, then generalize

## Rhythm and Flow

### The TDD Rhythm

Experienced TDD practitioners get into a flow:
- RED: 30 seconds to 2 minutes
- GREEN: 30 seconds to 5 minutes
- REFACTOR: 30 seconds to 5 minutes
- Repeat

**If any step takes longer**, you've probably taken too big a step.

### Signs You're Doing It Right

- Tests are passing most of the time
- Commits are small and frequent
- You feel confident making changes
- Design emerges organically
- You rarely need the debugger
- Refactoring feels safe and easy

### Signs You're Doing It Wrong

- Tests stay red for hours
- Afraid to refactor
- Tests break when you refactor
- Large commits with many changes
- Don't know where to start next
- Constantly using the debugger

## Resources

- **Kent Beck's "Test Driven Development: By Example"** - The canonical TDD book
- **Kent Beck's "Canon TDD"** - Modern definition: https://tidyfirst.substack.com/p/canon-tdd
- **Martin Fowler's "Refactoring"** - Catalog of structural changes
- **Kent Beck's "Tidy First?"** - When and how to make structural changes

## Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ✅ Store AI planning docs in `history/` directory
- ✅ Keep CRC cards conceptual, in the `<crc>`/`</crc>` two-key YAML format
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems
- ❌ Do NOT clutter repo root with planning documents

## Final Thoughts

**On Fear:**
Kent Beck believes TDD eliminates fear in programming, helping developers tackle difficult challenges with confidence rather than tentative, grumpy behavior.

**On Feedback:**
TDD provides frequent feedback which helps catch errors much sooner and allows making consequential programming decisions more quickly.

**On Design:**
There are two kinds of changes - behavior changes and structure changes. Always make one kind or the other, never both at the same time.

**On Steps:**
The initial step in TDD is to list all expected variants in the new behavior through behavioral analysis - thinking of all different cases where the behavior change should work.

Remember: **Clean code that works - now.** That's the goal. TDD is the path.
