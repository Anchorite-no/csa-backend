import codecs
import os
import subprocess
from functools import cache, lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CSA_SECRET_KEY: str = codecs.encode(os.urandom(32), "hex").decode()
    CSA_SECRET_KEY_ADMIN: str = codecs.encode(os.urandom(32), "hex").decode()
    DB_PATH: str = "sqlite:///data.sqlite"
    WEIXIN_APP_ID: str = ""
    WEIXIN_APP_SECRET: str = ""
    CAS_APP_ID: str = ""
    CAS_APP_SECRET: str = ""
    CAS_REDIRECT_URI: str = ""

    class Config:
        env_file = ".env"

    def __getitem__(self, item: str):
        return getattr(self, item)


def get_secret_key() -> str:
    return get_config("CSA_SECRET_KEY")

def get_secret_key_admin() -> str:
    return get_config("CSA_SECRET_KEY_ADMIN")

@lru_cache()
def get_config(item: Optional[str] = None):
    if item:
        return Settings()[item]
    return Settings()


@cache
def get_version() -> str:
    cmd = "git rev-parse --short HEAD"
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
    return proc.stdout.decode().strip()
