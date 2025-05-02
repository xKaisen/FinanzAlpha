from cx_Freeze import setup, Executable
import sys, os

# Sicherstellen, dass sqlite3 korrekt gebündelt wird
os.environ['TCL_LIBRARY'] = os.path.join(sys.base_prefix, 'tcl', 'tcl8.6')
os.environ['TK_LIBRARY'] = os.path.join(sys.base_prefix, 'tcl', 'tk8.6')

build_exe_options = {
    "packages": ["sqlite3", "os", "sys", "shutil"],
    "include_files": [
        ("finanz_app.db", "finanz_app.db"),
    ]
}

# GUI-Exe ohne Konsole
base = "Win32GUI" if sys.platform == "win32" else None

setup(
    name="FinanzApp",
    version="1.0.0",
    description="Meine Finanzanwendung",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            script="main.py",
            base=base,
            target_name="FinanzApp.exe"
        )
    ],
)
