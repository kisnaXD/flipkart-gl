"""Entry point: optional train, then start dashboard."""

import os

import uvicorn


def main() -> None:
    if os.environ.get("GRIDLOCK_TRAIN", "").lower() in ("1", "true", "yes"):
        from src.pipeline import run

        print("Training pipeline...")
        run()

    host = os.environ.get("GRIDLOCK_HOST", "127.0.0.1")
    port = int(os.environ.get("GRIDLOCK_PORT", "8000"))
    print(f"\nStarting dashboard at http://{host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
