import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import FileResponse

router = APIRouter()

IMAGES_DIR = Path("uploads/images")


@router.get("/images")
async def get_image(name: str = Query(..., description="图片文件名或相对路径")):
    try:
        full_path = IMAGES_DIR / name
        
        if not str(full_path.resolve()).startswith(str(IMAGES_DIR.resolve())):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image file not found"
            )
        
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
        if full_path.suffix.lower() not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type"
            )
        
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
            detail=f"Error occurred when getting image: {e}"
        )
