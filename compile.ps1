py.exe -m pip install nuitka
py.exe -m nuitka --standalone --onefile --lto=yes --windows-disable-console --enable-plugin=tk-inter --enable-plugin=numpy --windows-icon-from-ico=icon.ico --include-data-files=icon.ico=icon.ico raidalyzer.py

.\venv\Scripts\python.exe .\setup.py build