import os
import sys
import raidalyzer

from cx_Freeze import setup, Executable

version = raidalyzer.RaidAlyzerApp.VERSION

tcl_dir = os.path.join(sys.base_prefix, 'tcl', 'tcl8.6')
tk_dir = os.path.join(sys.base_prefix, 'tcl', 'tk8.6')

build_exe_options = {
    "packages": ["os", "tkinter", "matplotlib", "numpy", "unittest"],
    "include_files": [
        "icon.ico",
        (tcl_dir, "lib/tcl8.6"),
        (tk_dir, "lib/tk8.6")
    ],
    "excludes": ["email", "http"],
}

base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="RaidAlyzer",
    version=version,
    description="RAID array testing and analysis tool",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "raidalyzer.py",
            base=base,
            icon="icon.ico",
            target_name="RaidAlyzer.exe"
        )
    ]
)