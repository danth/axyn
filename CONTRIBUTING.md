## Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
with these types:

- `build`: Changes to dependencies or build system settings
- `ci`: Changes to continuous integration settings
- `docs`: Changes that only affect documentation
- `feat`: New features
- `fix`: Bug fixes
- `perf`: Improvements to performance without changing behaviour
- `refactor`: Improvements to code structure without changing behaviour
- `style`: Improvements to code formatting without changing its meaning
- `test`: Changes that only affect tests

Scopes are optional and have no predefined choices, but can be used to provide
context for the commit title.

## Type Hints

All code should use appropriate type hints. Names that are only used for type
checking should be imported inside an `if TYPE_CHECKING:` block, with
`from __future__ import annotations` outside the block to prevent errors at
runtime.

