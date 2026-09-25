"""Print the greeting stored in greeting.txt."""
from pathlib import Path

GREETING_FILE = Path(__file__).resolve().parent / "greeting.txt"


def main():
    print(GREETING_FILE.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    main()
