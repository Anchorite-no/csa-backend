from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from models import get_db
from misc.auth import get_current_admin
from misc.dingtalk import send_dingtalk_message, send_dingtalk_message_to_user
from config import get_dingtalk_config, update_dingtalk_config

router = APIRouter()


class DingTalkConfigRequest(BaseModel):
    appid: Optional[str] = None
    appkey: Optional[str] = None
    secret: Optional[str] = None
    enabled: Optional[bool] = None


class DingTalkMessageRequest(BaseModel):
    user_ids: List[str]
    title: str
    description: str
    link: Optional[str] = ""


class DingTalkSingleMessageRequest(BaseModel):
    user_id: str
    title: str
    description: str
    link: Optional[str] = ""


@router.get("/config")
def get_config(
    # current_admin: int = Depends(get_current_admin)
):
    """获取钉钉配置"""
    config = get_dingtalk_config()
    return {
        "appid": config.appid,
        "appkey": "***" if config.appkey else None,  # 隐藏敏感信息
        "secret": "***" if config.secret else None,  # 隐藏敏感信息
        "enabled": config.enabled,
        "configured": config.is_configured()
    }


@router.put("/config")
def update_config(config_data: DingTalkConfigRequest,
    # current_admin: int = Depends(get_current_admin)
):
    """更新钉钉配置"""
    try:
        update_dingtalk_config(
            appid=config_data.appid,
            appkey=config_data.appkey,
            secret=config_data.secret,
            enabled=config_data.enabled
        )
        return {"message": "配置更新成功"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"配置更新失败: {str(e)}"
        )


@router.post("/send_message")
def send_message(message_data: DingTalkMessageRequest,
    # current_admin: int = Depends(get_current_admin)
):
    """发送钉钉消息给多个用户"""
    try:
        success = send_dingtalk_message(
            user_ids=message_data.user_ids,
            title=message_data.title,
            description=message_data.description,
            link=message_data.link or ""
        )
        
        if success:
            return {"message": "消息发送成功", "success": True}
        else:
            return {"message": "消息发送失败", "success": False}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"消息发送失败: {str(e)}"
        )


@router.post("/send_single_message")
def send_single_message(message_data: DingTalkSingleMessageRequest,
    # current_admin: int = Depends(get_current_admin)
):
    """发送钉钉消息给单个用户"""
    try:
        success = send_dingtalk_message_to_user(
            user_id=message_data.user_id,
            title=message_data.title,
            description=message_data.description,
            link=message_data.link or ""
        )
        
        if success:
            return {"message": "消息发送成功", "success": True}
        else:
            return {"message": "消息发送失败", "success": False}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"消息发送失败: {str(e)}"
        )


@router.post("/test_connection")
def test_connection(
    # current_admin: int = Depends(get_current_admin)
):
    """测试钉钉连接"""
    try:
        config = get_dingtalk_config()
        if not config.is_configured():
            return {"message": "配置不完整", "success": False}
        
        if not config.enabled:
            return {"message": "钉钉功能已禁用", "success": False}
        
        # 发送测试消息给管理员
        success = send_dingtalk_message_to_user(
            user_id="0010449",  
            title="CSA系统钉钉连接测试",
            description="这是一条测试消息，用于验证钉钉OA连接是否正常。",
            link=""
        )
        
        if success:
            return {"message": "连接测试成功", "success": True}
        else:
            return {"message": "连接测试失败", "success": False}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"连接测试失败: {str(e)}"
        )
