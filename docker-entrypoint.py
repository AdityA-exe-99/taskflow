import os
import subprocess
import sys


def main():
    command = sys.argv[1:]

    if not command:
        raise SystemExit("No startup command was provided.")

    if command[0] == "gunicorn":
        print("Applying database migrations...", flush=True)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "flask",
                "--app",
                "app",
                "db",
                "upgrade",
            ],
            check=False,
        )

        if result.returncode != 0:
            print(
                "Database migration failed; application startup stopped.",
                file=sys.stderr,
                flush=True,
            )
            raise SystemExit(result.returncode)

        print(
            "Database migrations complete. Starting Gunicorn.",
            flush=True,
        )

    os.execvp(command[0], command)


if __name__ == "__main__":
    main()