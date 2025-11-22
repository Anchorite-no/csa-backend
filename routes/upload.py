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
                for item in zip_ref.infolist():
                    encoded_name = item.filename
                    try:
                        decoded_name = encoded_name.encode('cp437').decode('utf-8')
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        try:
                            decoded_name = encoded_name.encode('cp437').decode('gbk')
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            # 最后尝试直接解码（保持原状）
                            decoded_name = encoded_name
                    item.filename = decoded_name
                    zip_ref.extract(item, extract_to)
        elif file_path.suffix.lower() == '.rar':
            with rarfile.RarFile(file_path, 'r') as rar_ref:
                rar_ref.extractall(extract_to)
        else:
            return False
        return True
    except Exception as e:
        print(f"Decompression failed: {e}")
        return False


def validate_structure(extract_path: Path) -> tuple[bool, str, Optional[Path]]:
    md_files = list(extract_path.glob("**/*.md")) # 递归搜索所有子目录
    if not md_files:
        return False, "未找到markdown文件", None
    
    if len(md_files) > 1:
        return False, "找到多个markdown文件，请确保只有一个", None
    
    md_file = md_files[0]
    
    """ 不再强制要求img文件夹
    img_dir = extract_path / "img"
    if not img_dir.exists() or not img_dir.is_dir():
        return False, "未找到img文件夹", None
    """

    return True, "", md_file


# 支持的图片格式后缀（常见的图片格式）
ALLOWED_IMAGE_EXTENSIONS = {
    # 常见网络图片格式
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'
}


def validate_image_path(img_path_str: str, base_dir: Path) -> tuple[bool, str]:
    """
    验证图片路径的安全性
    
    Args:
        img_path_str: markdown 中的图片路径
        base_dir: 基础目录（解压目录）
    
    Returns:
        (is_valid, error_message)
        - is_valid: True 表示路径安全，False 表示路径不安全
        - error_message: 验证失败时的错误信息
    """
    # 检查是否为绝对路径
    if img_path_str.startswith('/') or img_path_str.startswith('\\'):
        return False, "不允许使用绝对路径"
    
    # 检查是否包含不合法的协议（如file:// 等）
    if 'file://' in img_path_str:
        return False, "不允许使用 file URL 链接"
    
    # 将字符串转换为 Path 对象以规范化路径
    img_path = Path(img_path_str)
    
    # 检查文件后缀是否为允许的图片格式
    file_suffix = img_path.suffix.lower()
    if not file_suffix:
        return False, "文件没有后缀名"
    
    if file_suffix not in ALLOWED_IMAGE_EXTENSIONS:
        return False, f"不支持的文件格式: {file_suffix}"
    
    # 检查是否为路径穿越攻击（../）
    # 使用 resolve() 后与 base_dir resolve() 比较，确保解析后的路径在 base_dir 内
    try:
        # 将相对路径与基础目录合并
        full_path = (base_dir / img_path).resolve()
        base_dir_resolved = base_dir.resolve()
        
        # 检查解析后的路径是否在 base_dir 内
        # 使用 is_relative_to() 检查（Python 3.9+）或手动检查
        try:
            full_path.relative_to(base_dir_resolved)
        except ValueError:
            return False, "不允许的路径穿越访问"
        
        return True, ""
    except Exception as e:
        return False, f"路径验证失败: {str(e)}"


def detect_and_read_file(file_path: Path) -> str:
    """
    智能检测文件编码并读取内容
    尝试多种常见编码：UTF-8, GBK, GB2312, Latin-1
    """
    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'big5', 'latin-1']
    
    for encoding in encodings:
        try:
            return file_path.read_text(encoding=encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    # 如果所有编码都失败，使用 UTF-8 并忽略错误
    print(f"Warning: Could not detect encoding for {file_path}, using utf-8 with errors='ignore'")
    return file_path.read_text(encoding='utf-8', errors='ignore')


def process_markdown_content(md_file: Path, img_dir: Path) -> tuple[str, str, str]:
    try:
        content = detect_and_read_file(md_file)
        
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else md_file.stem
        
        def replace_image_link(match):
            alt_text = match.group(1)
            img_path_str = match.group(2)
            
            # 验证路径安全性
            is_valid, error_msg = validate_image_path(img_path_str, img_dir)
            if not is_valid:
                print(f"Warning: {error_msg}, 图片路径: {img_path_str}")
                return match.group(0)  # 保持原样，跳过不安全的路径
            
            img_path = Path(img_path_str)

            if (img_dir / img_path).exists():
                img_file = img_dir / img_path
                file_ext = img_file.suffix
                unique_name = f"{uuid.uuid4()}{file_ext}"
                new_img_path = IMAGES_DIR / unique_name # 这里后续要加一个nid目录

                # 这里后续就不要直接copy过去，也要做一个tempdir
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
            detail=f"Failed to process markdown file: {e}"
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
            detail="Current user does not have permission to perform this operation"
        )
    
    if type not in ['news', 'event']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid type parameter"
        )
    
    if not (file.filename.endswith('.zip') or file.filename.endswith('.rar')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only zip and rar format archives are supported"
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
                detail="Archive decompression failed"
            )
        
        is_valid, error_msg, md_file = validate_structure(extract_path)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        base_dir = md_file.parent
        title, content, first_image = process_markdown_content(md_file, base_dir)
        
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
            detail=f"Error occurred when processing file: {e}"
        )
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
