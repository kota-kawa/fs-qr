# Repository Guidelines

## Project Structure & Module Organization
The Flask entry point is `app.py`, which wires Blueprints from `Core/`, `Group/`, `Note/`, `Admin/`, and `Articles/`. Shared database helpers live in `fs_data.py`, while module-specific data code resides inside each package (for example, `Group/group_data.py`). HTML templates sit in per-module `templates/` folders, with shared layouts in `templates/`, and static assets in `static/`. Database bootstrap SQL is housed in `db_init/` for the MySQL container.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` creates and activates a local virtualenv; install dependencies inside it.
- `pip install -r requirements.txt` installs Flask, SQLAlchemy, apscheduler, and other dependencies.
- `FLASK_APP=app.py flask run` starts the app with the default configuration—useful for quick, local iteration without Docker.
- `docker-compose up --build` mirrors production, launching the Flask app and MySQL defined in `docker-compose.yml`.
- `python app.py` runs the development server with the background scheduler and static cache-busting enabled.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation. Use `snake_case` for functions, blueprint factories, and filenames (`group_app.py`), and `PascalCase` for classes. Jinja templates adopt hyphenated names (e.g., `fs-qr.html`) to match exposed routes. Keep Blueprint registration inside each package’s `__init__.py` minimal and delegate route logic to `*_app.py`. Align logging changes with `log_config.py` so handlers stay consistent across modules.

## Testing Guidelines
Automated tests are not yet present; smoke-test the primary flows (`/fs-qr`, `/group`, `/note`, `/admin`) locally or via Docker. When introducing features, add `pytest` modules under `tests/` named `test_<area>.py`. Guard against regressions by validating teardown-driven session cleanup and the Note module’s collaborative editing. Document any manual verification steps in your PR until automated coverage is in place.

## Commit & Pull Request Guidelines
Existing commits favor concise, imperative summaries (for example, “Add site operator page”) with optional Japanese context. Keep message bodies focused on rationale and side effects. For pull requests, include: a feature summary, configuration or migration notes, manual test evidence (URLs exercised, screenshots for UI tweaks), and links to related issues. Request reviews from maintainers who own the affected module.

## Security & Configuration Tips
Do not commit real `.env` content; use the README template and rotate secrets regularly. Keep file uploads constrained through `app.config['MAX_CONTENT_LENGTH']`, mirroring any changes in Docker overrides. When updating MySQL schemas, revise `db_init/` scripts and describe backward-compatibility considerations in the PR.
