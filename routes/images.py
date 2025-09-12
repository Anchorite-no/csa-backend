import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import FileResponse

router = APIRouter()

# 配置图片存储目录
IMAGES_DIR = Path("uploads/images")


@router.get("/images")
async def get_image(name: str = Query(..., description="图片文件名或相对路径")):
    """
    获取图片文件
    name: 图片文件名或相对路径，例如 "8d1441da-6e01-4336-ba1a-2f15e93e027c.png" 或 "2025/09/12/8d1441da-6e01-4336-ba1a-2f15e93e027c.png"
    """
    try:
        # 构建完整的文件路径
        full_path = IMAGES_DIR / name
        
        # 安全检查：确保文件在允许的目录内
        if not str(full_path.resolve()).startswith(str(IMAGES_DIR.resolve())):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="访问被拒绝"
            )
        
        # 检查文件是否存在
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="图片文件未找到"
            )
        
        # 检查文件扩展名
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
        if full_path.suffix.lower() not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的文件类型"
            )
        
        # 返回文件
        return FileResponse(
            path=str(full_path),
            media_type="image/png" if full_path.suffix.lower() == '.png' else "image/jpeg",
            filename=full_path.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取图片时发生错误: {e}"
        )
