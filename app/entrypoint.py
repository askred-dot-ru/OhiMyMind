import subprocess
import sys

from app.main import run


def main() -> None:
    subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"])
    run()


if __name__ == "__main__":
    main()
