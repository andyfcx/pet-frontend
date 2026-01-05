pyinstaller \
  --onefile \
  --windowed \
  --add-binary ".venv/lib/python3.12/site-packages/biometeo/*.so:biometeo" \
  biometeo-front.py