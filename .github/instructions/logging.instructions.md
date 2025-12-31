---
applyTo: **/*.py
name: Python Logging Best Practices
description: Guidelines for effective logging in Python projects.
---
Use lazy % formatting in logging functions to avoid unnecessary string interpolation when the log level is disabled. For example, use:

```python
logger.debug("Processing place ID: %s", place_id)
```
