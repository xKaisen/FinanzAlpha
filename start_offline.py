# start_offline.py
import os
os.environ.setdefault("APP_MODE", "offline")

from run import run_ui  # oder direkt aus deinem CLI-Entrypoint
if __name__ == "__main__":
    run_ui()
