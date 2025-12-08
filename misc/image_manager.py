import re
import os
from pathlib import Path
from typing import Set, List
from urllib.parse import urlparse

# 配置图片存储目录
IMAGES_DIR = Path("uploads/images")


def extract_image_urls_from_content(content: str) -> Set[str]:
    """从markdown内容中提取所有图片URL"""
    if not content:
        return set()
    
    # 匹配markdown图片语法: ![alt](url)
    image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    matches = re.findall(image_pattern, content)
    
    # 提取URL并过滤出本地上传的图片
    image_urls = set()
    for alt_text, url in matches:
        if url.startswith('/uploads/images/'):
            image_urls.add(url)
    
    return image_urls


def extract_image_url_from_field(image_field: str) -> Set[str]:
    """从头图字段中提取图片URL"""
    if not image_field or not image_field.startswith('/uploads/images/'):
        return set()
    return {image_field}


def get_image_path_from_url(url: str) -> Path:
    """从URL获取本地文件路径"""
    if not url.startswith('/uploads/images/'):
        return None
    
    # 移除URL前缀，获取相对路径
    relative_path = url.replace('/uploads/images/', '')
    return IMAGES_DIR / relative_path


def delete_image_file(image_url: str) -> bool:
    """删除单个图片文件"""
    try:
        image_path = get_image_path_from_url(image_url)
        if image_path and image_path.exists():
            image_path.unlink()
            return True
    except Exception as e:
        print(f"删除图片文件失败 {image_url}: {e}")
    return False


def delete_image_files(image_urls: Set[str]) -> int:
    """批量删除图片文件，返回成功删除的数量"""
    deleted_count = 0
    for url in image_urls:
        if delete_image_file(url):
            deleted_count += 1
    return deleted_count


def cleanup_unused_images(old_content: str, new_content: str, old_image: str = "", new_image: str = "") -> int:
    """
    清理不再使用的图片文件
    返回删除的图片数量
    """
    # 提取旧内容中的图片URL
    old_content_images = extract_image_urls_from_content(old_content)
    old_field_images = extract_image_url_from_field(old_image)
    old_images = old_content_images | old_field_images
    
    # 提取新内容中的图片URL
    new_content_images = extract_image_urls_from_content(new_content)
    new_field_images = extract_image_url_from_field(new_image)
    new_images = new_content_images | new_field_images
    
    # 找出不再使用的图片
    unused_images = old_images - new_images
    
    # 删除不再使用的图片
    return delete_image_files(unused_images)


import shutil

def cleanup_all_images(content: str, image: str = "") -> int:
    """
    清理内容中的所有图片文件（用于删除操作）
    返回删除的图片数量
    """
    content_images = extract_image_urls_from_content(content)
    field_images = extract_image_url_from_field(image)
    all_images = content_images | field_images
    
    return delete_image_files(all_images)


def delete_draft_folder(type: str, id: int) -> int:
    """
    删除草稿对应的图片文件夹
    type: 'news' or 'event'
    id: nid or eid
    返回删除的文件数量（估算）
    """
    count = 0
    paths_to_check = []
    
    # 1. New structure: uploads/images/{type}/{id}
    paths_to_check.append(IMAGES_DIR / type / str(id))
    
    # 2. Old structure (potential backward compatibility): uploads/images/{id}
    # Only check this if type is news, as implied by upload.py logic, but safer to check both if needed.
    # However, upload.py only checks (IMAGES_DIR / str(nid)) for news.
    if type == 'news':
        paths_to_check.append(IMAGES_DIR / str(id))
        
    for path in paths_to_check:
        if path.exists() and path.is_dir():
            try:
                # Count files before deleting for reporting
                for _ in path.glob('**/*'):
                    if _.is_file():
                        count += 1
                shutil.rmtree(path)
            except Exception as e:
                print(f"Failed to delete draft folder {path}: {e}")
                
    return count
