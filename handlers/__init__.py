from config import Config
from services.article_parser import ArticleParser
from services.obsidian import ObsidianVault
from services.sync import VaultSync

from .llm_handler import LLMHandler

config = Config()
llm_handler = LLMHandler()
vault = ObsidianVault(config.OBSIDIAN_VAULT_PATH, inbox_dir="Входящие")
vault_sync = VaultSync(
    config.OBSIDIAN_VAULT_PATH,
    config.ICLOUD_VAULT_PATH,
    config.RCLONE_REMOTE,
)
article_parser = ArticleParser()
