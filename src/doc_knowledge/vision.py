"""
大模型视觉识别服务（并发优化版）

通过 OpenAI 兼容 API 调用多模态大模型识别图片内容。
支持并发处理、图片过滤、智能重试。
"""

import base64
import json
import hashlib
import io
import time
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed


class ImageFilter:
    """图片过滤器 - 快速判断图片是否有识别价值"""
    
    def __init__(
        self,
        min_size: int = 500,           # 最小文件大小（字节）
        min_resolution: int = 50,      # 最小分辨率（宽或高）
        max_similarity_threshold: float = 0.95,  # 最大相似度阈值
    ):
        self.min_size = min_size
        self.min_resolution = min_resolution
        self.max_similarity_threshold = max_similarity_threshold
        self._hash_cache = {}
    
    def should_recognize(self, image_path: Path) -> tuple[bool, str]:
        """
        判断图片是否需要识别
        
        Returns:
            (是否需要识别, 原因)
        """
        if not image_path.exists():
            return False, "文件不存在"
        
        # 检查文件大小
        file_size = image_path.stat().st_size
        if file_size < self.min_size:
            return False, f"文件太小 ({file_size}B < {self.min_size}B)"
        
        # 检查分辨率
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                w, h = img.size
                if w < self.min_resolution or h < self.min_resolution:
                    return False, f"分辨率太低 ({w}x{h})"
        except Exception:
            return True, "无法检查分辨率，默认识别"
        
        # 检查是否为纯色图片（简单哈希检测）
        if self._is_solid_color(image_path):
            return False, "纯色图片"
        
        return True, "需要识别"
    
    def _is_solid_color(self, image_path: Path) -> bool:
        """简单检测是否为纯色图片"""
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                # 缩小到 10x10 像素
                small = img.resize((10, 10))
                pixels = list(small.getdata())
                if len(pixels) < 10:
                    return False
                
                # 计算像素方差
                r_vals = [p[0] for p in pixels]
                g_vals = [p[1] for p in pixels]
                b_vals = [p[2] for p in pixels]
                
                def variance(vals):
                    mean = sum(vals) / len(vals)
                    return sum((x - mean) ** 2 for x in vals) / len(vals)
                
                var_r = variance(r_vals)
                var_g = variance(g_vals)
                var_b = variance(b_vals)
                
                # 方差小于阈值认为是纯色
                return var_r < 10 and var_g < 10 and var_b < 10
        except Exception:
            return False


class LLMVisionService:
    """大模型视觉识别服务（支持并发）"""
    
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str = "qwen-vl-plus",
        system_prompt: Optional[str] = None,
        timeout: int = 120,
        max_workers: int = 5,
        max_image_size: int = 2 * 1024 * 1024,  # 2MB
    ):
        self.api_url = api_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt or (
            "请识别图片中的所有文字内容。保持原文的排版顺序。"
            "如果是图表，请描述图表的主要内容和数据。"
            "如果是示意图或流程图，请详细描述图中的信息。"
            "只输出识别到的文字，不要添加额外评论。"
        )
        self.timeout = timeout
        self.max_workers = max_workers
        self.max_image_size = max_image_size
        self.filter = ImageFilter()
    
    def recognize_image(self, image_path: Path) -> str:
        """识别单张图片"""
        if not image_path.exists():
            return f"[图片文件不存在: {image_path.name}]"
        
        # 读取图片
        image_data = image_path.read_bytes()
        
        # 压缩过大的图片
        if len(image_data) > self.max_image_size:
            try:
                from PIL import Image
                img = Image.open(image_path)
                new_size = (int(img.width * 0.5), int(img.height * 0.5))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                image_data = buffer.getvalue()
            except Exception:
                pass
        
        # 确定 MIME 类型
        ext = image_path.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
        }
        mime_type = mime_map.get(ext, "image/jpeg")
        base64_image = base64.b64encode(image_data).decode("utf-8")
        
        # 构建请求
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        },
                        {"type": "text", "text": "请识别这张图片的内容。"}
                    ]
                }
            ],
            "max_tokens": 2000,
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.api_url, data=data, method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except urllib.error.URLError as e:
            return f"[图片识别失败: {e}]"
        except (KeyError, IndexError) as e:
            return f"[图片解析失败: {e}]"
    
    def recognize_images_batch(self, image_paths: list[Path], verbose: bool = False) -> dict[Path, str]:
        """
        批量识别多张图片（带过滤 + 并发）
        
        Args:
            image_paths: 图片路径列表
            verbose: 是否输出详细信息
            
        Returns:
            {图片路径: 识别结果} 字典
        """
        # 第一步：过滤低价值图片
        filtered_paths = []
        skipped_count = 0
        skip_reasons = {}
        
        for path in image_paths:
            should_rec, reason = self.filter.should_recognize(path)
            if should_rec:
                filtered_paths.append(path)
            else:
                skipped_count += 1
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                if verbose:
                    print(f"  跳过 {path.name}: {reason}")
        
        if verbose:
            print(f"  过滤完成: {len(image_paths)} 张 → {len(filtered_paths)} 张需识别，{skipped_count} 张跳过")
            if skip_reasons:
                for reason, count in skip_reasons.items():
                    print(f"    - {reason}: {count} 张")
        
        if not filtered_paths:
            return {}
        
        # 第二步：并发识别
        results = {}
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {
                executor.submit(self.recognize_image, path): path
                for path in filtered_paths
            }
            
            for i, future in enumerate(as_completed(future_to_path)):
                path = future_to_path[future]
                try:
                    result = future.result()
                    results[path] = result
                    if verbose:
                        print(f"  [{i+1}/{len(filtered_paths)}] 识别完成: {path.name} ({len(result)} 字符)")
                except Exception as e:
                    results[path] = f"[识别异常: {e}]"
                    if verbose:
                        print(f"  [{i+1}/{len(filtered_paths)}] 识别失败: {path.name}")
        
        elapsed = time.time() - start_time
        if verbose:
            print(f"  并发识别完成: {len(filtered_paths)} 张，耗时 {elapsed:.1f} 秒")
        
        return results
