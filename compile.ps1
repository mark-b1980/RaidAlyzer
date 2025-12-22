py.exe -m pip install nuitka
py.exe -m nuitka --standalone --onefile --lto=yes --windows-disable-console --enable-plugin=tk-inter --windows-icon-from-ico=icon.ico raidalyzer.py