---
applyTo: **/*.py
name: Solid Python Coding Guidelines
description: This file describes the Solid coding style for Python files in the project.
---
## GitHub Copilot Instructions — SOLID Python

### General Philosophy

* Write **clean, explicit, readable Python**.
* Favor **composition over inheritance**.
* Optimize for **testability**, **maintainability**, and **clarity** over brevity.
* Avoid “clever” solutions if they reduce readability.

---

## Single Responsibility Principle (SRP)

* Each **class** and **function** must have **one clearly defined responsibility**.
* If a class description requires the word **“and”**, split it.
* Separate:

  * Business logic
  * I/O (files, HTTP, databases)
  * Data transformation
  * Configuration

**Guidelines**

* Functions should usually be **< 30 lines**
* Classes should usually be **< 200 lines**
* Prefer small helper objects over large utility modules

---

## Open/Closed Principle (OCP)

* Code should be **open for extension, closed for modification**
* Extend behavior using:

  * New classes
  * Strategy patterns
  * Dependency injection
* Avoid modifying existing logic to add new behavior

**Guidelines**

* Avoid large `if/elif` or `match` blocks for behavior selection
* Prefer polymorphism or callable injection
* Use registries or mappings for extensibility

---

## Liskov Substitution Principle (LSP)

* Subclasses must be **fully substitutable** for their base classes
* Do not weaken preconditions or strengthen postconditions
* Avoid raising new exceptions not defined by the base class contract

**Guidelines**

* Respect base class method signatures and return types
* Do not override methods just to raise `NotImplementedError`
* Prefer `abc.ABC` and `@abstractmethod`

---

## Interface Segregation Principle (ISP)

* Prefer **small, focused interfaces** over large ones
* Do not force implementations to depend on unused methods

**Guidelines**

* Use multiple small `Protocol` or `ABC` interfaces instead of one large one
* Prefer structural subtyping via `typing.Protocol` when possible
* Keep interfaces minimal and intention-revealing

---

## Dependency Inversion Principle (DIP)

* Depend on **abstractions**, not concrete implementations
* High-level logic should not import low-level modules directly

**Guidelines**

* Inject dependencies via:

  * Constructor arguments
  * Function parameters
* Avoid creating concrete dependencies inside business logic
* Prefer passing interfaces, callables, or factories

---

## Typing & Contracts

* Use **type hints everywhere**
* Prefer `Protocol` over inheritance for behavior contracts
* Use `@dataclass` for immutable data structures
* Avoid runtime type checks where static typing suffices

---

## Error Handling

* Raise **domain-specific exceptions**
* Do not catch exceptions unless you can handle them meaningfully
* Avoid bare `except Exception`
* Let lower layers translate errors into domain-level exceptions

---

## Testing & Design for Testability

* Code must be **unit-testable without mocks for core logic**
* Avoid global state and singletons
* Pure functions are preferred when possible

**Guidelines**

* Separate side effects from logic
* Accept collaborators as parameters
* Design functions that return values rather than mutating state

---

## Python-Specific Best Practices

* Prefer explicit over implicit
* Avoid magic numbers; use named constants
* Avoid circular imports
* Keep modules focused and cohesive
* Use `__all__` in public modules

---

## Documentation

* Every public class and function must have a docstring explaining:

  * Purpose
  * Inputs
  * Outputs
* Docstrings should describe **intent**, not implementation

---

## Copilot Behavior Instructions

When generating code:

* Prefer **SOLID-compliant designs**
* Suggest refactors when a principle is violated
* Avoid monolithic classes or functions
* Ask for clarification if responsibilities are unclear
* Favor maintainable architecture over quick fixes

---

### Optional: Short Reminder Block

> If a change increases coupling, reduces testability, or adds multiple responsibilities, **stop and refactor**.
