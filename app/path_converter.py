import os
from app.config import settings


class PathConverter:
    def __init__(self):
        self.root_dir = os.path.abspath(settings.root_dir)
        self.public_windows = getattr(settings, "public_smb_windows", None)
        self.public_mac = getattr(settings, "public_smb_mac", None)

    def gerar_caminho_publico(self, caminho_original: str, sistema: str = "windows") -> str:

        caminho_original = os.path.abspath(caminho_original)

        if not caminho_original.startswith(self.root_dir):
            return caminho_original

        # Remove apenas o prefixo ROOT_DIR
        caminho_relativo = caminho_original[len(self.root_dir):].lstrip("/\\")
        caminho_relativo = caminho_relativo.replace("\\", "/")

        if sistema.lower() == "windows" and self.public_windows:
            caminho_formatado = caminho_relativo.replace("/", "\\")
            return f"{self.public_windows}\\{caminho_formatado}"

        elif sistema.lower() == "mac" and self.public_mac:
            return f"{self.public_mac}/{caminho_relativo}"

        return caminho_original


def detectar_sistema(user_agent: str) -> str:
    user_agent = (user_agent or "").lower()

    if "windows" in user_agent:
        return "windows"
    elif "mac" in user_agent:
        return "mac"

    return "windows"