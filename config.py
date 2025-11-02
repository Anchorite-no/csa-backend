import codecs
import os
import subprocess
from functools import cache, lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CSA_SECRET_KEY: str = codecs.encode(os.urandom(32), "hex").decode()
    CSA_SECRET_KEY_ADMIN: str = codecs.encode(os.urandom(64), "hex").decode()
    DB_PATH: str = "sqlite:///data.sqlite"
    WEIXIN_APP_ID: str = ""
    WEIXIN_APP_SECRET: str = ""
    CAS_APP_ID: str = ""
    CAS_APP_SECRET: str = ""
    CAS_REDIRECT_URI: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 995
    SMTP_USER: str = ""
    SMTP_PASSWD: str = ""
    ADMIN_PASSWORD: str = "ZJUCSA@2025_90381664123847"

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

class DingTalkConfig:
    """钉钉配置类"""
    
    def __init__(self):
        self.appid = os.getenv('DINGTALK_APPID', 'ucxaccyfkmxl')
        self.appkey = os.getenv('DINGTALK_APPKEY', 'qmz9gYg6vQ4TBgiG')
        self.secret = os.getenv('DINGTALK_SECRET', '6595133c02dbf5227369')
        
        self.enabled = os.getenv('DINGTALK_ENABLED', 'true').lower() == 'true'
    
    def is_configured(self) -> bool:
        """检查配置是否完整"""
        return all([self.appid, self.appkey, self.secret])
    
    def get_config_dict(self) -> dict:
        """获取配置字典"""
        return {
            'appid': self.appid,
            'appkey': self.appkey,
            'secret': self.secret,
            'enabled': self.enabled
        }


# 全局配置实例
dingtalk_config = DingTalkConfig()


def get_dingtalk_config() -> DingTalkConfig:
    """获取钉钉配置实例"""
    return dingtalk_config


def update_dingtalk_config(appid: Optional[str] = None, 
                          appkey: Optional[str] = None, 
                          secret: Optional[str] = None,
                          enabled: Optional[bool] = None):
    """
    更新钉钉配置
    
    Args:
        appid: 应用ID
        appkey: 应用密钥
        secret: 签名密钥
        enabled: 是否启用
    """
    if appid is not None:
        dingtalk_config.appid = appid
    if appkey is not None:
        dingtalk_config.appkey = appkey
    if secret is not None:
        dingtalk_config.secret = secret
    if enabled is not None:
        dingtalk_config.enabled = enabled
