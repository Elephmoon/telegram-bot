import logging
import shutil
import subprocess
from pathlib import Path
from typing import Tuple  # ← добавить

logger = logging.getLogger(__name__)


class VaultSync:
    def __init__(self, vault_path: str, icloud_path: str = "", rclone_remote: str = ""):
        self.vault_path = Path(vault_path)
        self.icloud_path = Path(icloud_path) if icloud_path else None
        self.rclone_remote = rclone_remote

    @property
    def is_configured(self) -> bool:
        return bool(self.icloud_path or self.rclone_remote)

    def sync(self) -> Tuple[bool, str]:  # ← Tuple
        if self.rclone_remote:
            return self._sync_rclone()
        if self.icloud_path:
            return self._sync_direct()
        return False, "Синхронизация не настроена."

    def _sync_rclone(self) -> Tuple[bool, str]:  # ← Tuple
        try:
            result = subprocess.run(
                [
                    "rclone",
                    "bisync",
                    str(self.vault_path),
                    self.rclone_remote,
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode == 0:
                return True, "✅ Синхронизация через rclone выполнена."
            if "resync" in result.stderr:
                return self._sync_rclone_resync()
            return False, f"❌ Ошибка rclone:\n```\n{result.stderr[:500]}\n```"
        except FileNotFoundError:
            return False, "❌ `rclone` не найден."
        except subprocess.TimeoutExpired:
            return False, "❌ Таймаут (180 сек)."
        except Exception as e:
            return False, f"❌ Ошибка: {e}"

    def _sync_rclone_resync(self) -> Tuple[bool, str]:  # ← Tuple
        try:
            result = subprocess.run(
                [
                    "rclone",
                    "bisync",
                    str(self.vault_path),
                    self.rclone_remote,
                    "--resync",
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode == 0:
                return True, "✅ Первичная синхронизация выполнена."
            return False, f"❌ Ошибка resync:\n```\n{result.stderr[:500]}\n```"
        except Exception as e:
            return False, f"❌ Ошибка: {e}"

    def _sync_direct(self) -> Tuple[bool, str]:  # ← Tuple
        try:
            if not self.icloud_path:
                return False, "iCloud path не задан."
            self.icloud_path.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                str(self.vault_path), str(self.icloud_path), dirs_exist_ok=True
            )
            return True, f"✅ Скопировано в iCloud:\n`{self.icloud_path}`"
        except Exception as e:
            return False, f"❌ Ошибка: {e}"
