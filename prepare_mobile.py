"""Generate Android launcher art and a persistent private release signing key."""
from pathlib import Path
import os
import secrets
import subprocess

from PyQt6.QtWidgets import QApplication
from ktx_app import app_icon


def main():
    root = Path(__file__).resolve().parent
    android = root / "mobile" / "android"
    app = QApplication([])
    resources = android / "app" / "src" / "main" / "res"
    for density, size in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        target = resources / f"mipmap-{density}" / "ic_launcher.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not app_icon(size).pixmap(size, size).save(str(target), "PNG"):
            raise RuntimeError(f"Could not render {target}")
    properties = android / "key.properties"
    key = android / "keystore" / "release.jks"
    if not properties.exists():
        if key.exists():
            raise RuntimeError("Signing key already exists. Restore key.properties instead of overwriting it.")
        key.parent.mkdir(exist_ok=True)
        password = secrets.token_urlsafe(32)
        keytool = Path(os.environ.get("JAVA_HOME", "C:/Program Files/Android/Android Studio/jbr")) / "bin" / "keytool.exe"
        # Passwords are passed via environment rather than process arguments.
        env = dict(os.environ, KTX_KEY_PASSWORD=password)
        subprocess.run([str(keytool), "-genkeypair", "-keystore", str(key), "-storepass:env", "KTX_KEY_PASSWORD",
                        "-keypass:env", "KTX_KEY_PASSWORD", "-alias", "ktx", "-keyalg", "RSA", "-keysize", "2048",
                        "-validity", "10000", "-dname", "CN=KTX Seat Watch", "-storetype", "JKS"],
                       env=env, check=True, capture_output=True)
        properties.write_text(f"storeFile=../keystore/release.jks\nstorePassword={password}\nkeyPassword={password}\nkeyAlias=ktx\n", encoding="utf-8")
    print("Android icons and release signing configuration are ready.")


if __name__ == "__main__":
    main()
