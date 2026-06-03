import subprocess
import sys


def main():
    result = subprocess.run(["alembic", "upgrade", "head"])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
