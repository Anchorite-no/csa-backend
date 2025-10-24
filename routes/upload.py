import os
import zipfile
import rarfile
import shutil
import uuid
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from misc.auth import get_current_admin
from models import get_db
from routes.admin import is_manager

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

IMAGES_DIR = Path("uploads/images")
IMAGES_DIR.mkdir(exist_ok=True)


def extract_archive(file_path: Path, extract_to: Path) -> bool:
    try:
        if file_path.suffix.lower() == '.zip':
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
        elif file_path.suffix.lower() == '.rar':
            with rarfile.RarFile(file_path, 'r') as rar_ref:
                rar_ref.extractall(extract_to)
        else:
            return False
        return True
    except Exception as e:
        print(f"解压失败: {e}")
        return False


def validate_structure(extract_path: Path) -> tuple[bool, str, Optional[Path]]:
    md_files = list(extract_path.glob("*.md"))
    if not md_files:
        return False, "未找到markdown文件", None
    
    if len(md_files) > 1:
        return False, "找到多个markdown文件，请确保只有一个", None
    
    md_file = md_files[0]
    
    img_dir = extract_path / "img"
    if not img_dir.exists() or not img_dir.is_dir():
        return False, "未找到img文件夹", None
    
    return True, "", md_file


def process_markdown_content(md_file: Path, img_dir: Path) -> tuple[str, str, str]:
    try:
        content = md_file.read_text(encoding='utf-8')
        
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else md_file.stem
        
        def replace_image_link(match):
            alt_text = match.group(1)
            img_path_str = match.group(2)
            img_path = Path(img_path_str)
            
            if (img_dir / img_path.name).exists():
                img_file = img_dir / img_path.name
                file_ext = img_file.suffix
                unique_name = f"{uuid.uuid4()}{file_ext}"
                new_img_path = IMAGES_DIR / unique_name
                
                shutil.copy2(img_file, new_img_path)
                
                return f"![{alt_text}](/uploads/images/{unique_name})"
            else:
                return match.group(0)  # 保持原样
        
        processed_content = re.sub(
            r'!\[([^\]]*)\]\(([^)]+)\)',
            replace_image_link,
            content
        )
        
        first_img_match = re.search(r'!\[([^\]]*)\]\(([^)]+)\)', processed_content)
        first_image = ""
        if first_img_match:
            first_image = first_img_match.group(2)
        
        return title, processed_content, first_image
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理markdown文件失败: {e}"
        )


@router.post("/parse")
async def parse_uploaded_file(
    file: UploadFile = File(...),
    type: str = Form(...),
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin)
):
    """解析上传的压缩包"""
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前用户没有权限进行此操作"
        )
    
    if type not in ['news', 'event']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的类型参数"
        )
    
    if not (file.filename.endswith('.zip') or file.filename.endswith('.rar')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持zip和rar格式的压缩包"
        )
    
    temp_id = str(uuid.uuid4())
    temp_dir = UPLOAD_DIR / temp_id
    temp_dir.mkdir(exist_ok=True)
    
    try:
        file_path = temp_dir / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        extract_path = temp_dir / "extracted"
        extract_path.mkdir(exist_ok=True)
        
        if not extract_archive(file_path, extract_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="压缩包解压失败"
            )
        
        is_valid, error_msg, md_file = validate_structure(extract_path)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        img_dir = extract_path / "img"
        title, content, first_image = process_markdown_content(md_file, img_dir)
        
        return {
            "success": True,
            "title": title,
            "content": content,
            "image": first_image,
            "message": "文件解析成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理文件时发生错误: {e}"
        )
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
