import PyInstaller.__main__
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

args = [
    os.path.join(script_dir, "main.py"),
    "--name", "PyCompare",
    "--onefile",
    "--windowed",
    "--noconsole",
    "--clean",
    "--hidden-import", "openpyxl",
    "--hidden-import", "pandas",
    "--hidden-import", "PIL",
    "--hidden-import", "PIL.Image",
    "--hidden-import", "PIL.ImageTk",
]

icon_path = os.path.join(script_dir, "icon", "IconaPyCompare.ico")
if os.path.exists(icon_path):
    args.extend(["--icon", icon_path])

for dirname in ("icon", "data"):
    src = os.path.join(script_dir, dirname)
    if os.path.exists(src):
        args.extend(["--add-data", f"{src}{os.pathsep}{dirname}"])

PyInstaller.__main__.run(args)
print("Build complete: dist/PyCompare.exe")
