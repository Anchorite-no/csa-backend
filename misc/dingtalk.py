import json
import base64
import requests
import hmac 
import hashlib
from typing import List, Optional
from config import get_dingtalk_config


class DingTalkMessenger:
    """钉钉OA消息发送器"""
    
    def __init__(self, appid: str, appkey: str, secret: str):
        """
        初始化钉钉消息发送器
        
        Args:
            appid: 应用ID
            appkey: 应用密钥
            secret: 签名密钥
        """
        self.appid = appid
        self.appkey = appkey
        self.secret = secret
        self.base_url = "https://api.zju.edu.cn/api"
    
    def get_token(self) -> Optional[str]:
        """
        获取访问令牌
        
        Returns:
            str: 访问令牌，失败时返回None
        """
        try:
            url = f"{self.base_url}/reqtoken"
            params = {
                'appid': self.appid,
                'appkey': self.appkey
            }
            
            response = requests.get(url, params=params, timeout=10)
            result = response.json()
            
            if result.get('result') == 'success':
                return result.get('data', {}).get('token')
            else:
                print(f'获取token失败: {result}')
                return None
                
        except Exception as e:
            print(f'获取token异常: {e}')
            return None
    
    def send_message(self, user_ids: List[str], title: str, description: str, link: str = "") -> bool:
        """
        发送钉钉OA消息
        
        Args:
            user_ids: 用户ID列表
            title: 消息标题
            description: 消息描述
            link: 消息链接（可选）
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 获取token
            token = self.get_token()
            if not token:
                return False
            
            # 准备消息数据
            data = {
                "token": token,
                "parameter": {
                    "appid": self.appid,
                    "userids": ",".join(user_ids),
                    "title": title,
                    "description": description,
                    "link": link
                }
            }
            
            # 生成签名
            code = base64.b64encode(json.dumps(data).encode('utf-8'))
            signature = base64.b64encode(
                hmac.new(self.secret.encode('utf-8'), code, hashlib.sha256).digest()
            )
            
            # 发送请求
            params = {
                "code": code.decode('utf-8'),
                "signature": signature.decode('utf-8')
            }
            
            response = requests.post(
                f"{self.base_url}/dingoamsg/service",
                data=params,
                timeout=10
            )
            
            result = response.json()
            
            if result.get('result') == 'success':
                print('消息发送成功')
                return True
            else:
                print(f'消息发送失败: {result}')
                return False
                
        except Exception as e:
            print(f'发送消息异常: {e}')
            return False
    
    def send_single_message(self, user_id: str, title: str, description: str, link: str = "") -> bool:
        """
        向单个用户发送消息
        
        Args:
            user_id: 用户ID
            title: 消息标题
            description: 消息描述
            link: 消息链接（可选）
            
        Returns:
            bool: 发送是否成功
        """
        return self.send_message([user_id], title, description, link)


# 创建默认实例
def get_default_messenger() -> DingTalkMessenger:
    """获取默认的钉钉消息发送器实例"""
    config = get_dingtalk_config()
    return DingTalkMessenger(config.appid, config.appkey, config.secret)

default_messenger = get_default_messenger()


def send_dingtalk_message(user_ids: List[str], title: str, description: str, link: str = "") -> bool:
    """
    发送钉钉消息的便捷函数
    
    Args:
        user_ids: 用户ID列表
        title: 消息标题
        description: 消息描述
        link: 消息链接（可选）
        
    Returns:
        bool: 发送是否成功
    """
    config = get_dingtalk_config()
    if not config.enabled:
        print("钉钉消息发送功能已禁用")
        return False
    
    if not config.is_configured():
        print("钉钉配置不完整")
        return False
    
    messenger = get_default_messenger()
    return messenger.send_message(user_ids, title, description, link)


def send_dingtalk_message_to_user(user_id: str, title: str, description: str, link: str = "") -> bool:
    """
    向单个用户发送钉钉消息的便捷函数
    
    Args:
        user_id: 用户ID
        title: 消息标题
        description: 消息描述
        link: 消息链接（可选）
        
    Returns:
        bool: 发送是否成功
    """
    config = get_dingtalk_config()
    if not config.enabled:
        print("钉钉消息发送功能已禁用")
        return False
    
    if not config.is_configured():
        print("钉钉配置不完整")
        return False
    
    messenger = get_default_messenger()
    return messenger.send_single_message(user_id, title, description, link)


# 示例用法
if __name__ == '__main__':
    # 使用默认配置发送消息
    success = send_dingtalk_message_to_user(
        user_id="0010449",
        title="网络空间安全协会钉钉OA测试",
        description="您有一门线上课程待学习",
        link="https://www.gov.cn/gongbao/content/2021/content_5623051.htm"
    )
    
    if success:
        print("消息发送成功！")
    else:
        print("消息发送失败！")
