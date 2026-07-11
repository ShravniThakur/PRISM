import base64
from app.crypto import signing
from pathlib import Path

pem = Path('app/sebi.pem').read_text()
msg = b'Hello World'
# I'll just print python signature to compare with JS output
print("Python Signature Base64:", signing.sign(pem, msg))
