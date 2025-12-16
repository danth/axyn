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
checking should be imported inside an `if TYPE_CHECKING:` block.

`from __future__ import annotations` is currently required to allow type hints
to be lazily evaluated, so they do not cause errors during normal usage. This
can be removed once we require Python 3.14 or higher.

