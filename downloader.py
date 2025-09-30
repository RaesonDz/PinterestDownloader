
"""
نظام تحميل فيديوهات Pinterest المتقدم
يستخدم web scraping وتحليل API calls للحصول على روابط الفيديوهات المباشرة
"""
import os
import logging
import re
import json
import asyncio
import aiohttp
import aiofiles
from typing import Optional, Dict, Any, List
import hashlib
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import time
import random
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)


class AdvancedPinterestDownloader:
    """نظام تحميل متقدم لفيديوهات Pinterest"""
    
    def __init__(self, download_dir: str = "downloads"):
        """
        تهيئة النظام المتقدم
        
        Args:
            download_dir: مجلد التحميل
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        
        self.ua = UserAgent()
        self.session = None
        
        # Pinterest API endpoints
        self.api_endpoints = {
            'pin_data': 'https://www.pinterest.com/resource/PinResource/get/',
            'video_data': 'https://www.pinterest.com/_ngjs/resource/PinResource/get/',
            'search': 'https://www.pinterest.com/resource/BaseSearchResource/get/'
        }
        
        # Headers متقدمة تحاكي المتصفح الحقيقي
        self.base_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
        logger.info(f"تم تهيئة النظام المتقدم: {download_dir}")
    
    async def __aenter__(self):
        """إنشاء جلسة HTTP عند دخول السياق"""
        connector = aiohttp.TCPConnector(
            limit=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
            ssl=False,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=60, connect=30)
        
        # إنشاء الجلسة مع دعم أفضل للتشفير
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.base_headers,
            auto_decompress=True,  # فك الضغط التلقائي
            trust_env=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """إغلاق الجلسة عند الخروج من السياق"""
        if self.session:
            await self.session.close()
    
    def _get_fresh_headers(self) -> Dict[str, str]:
        """إنشاء headers جديدة لكل طلب"""
        headers = self.base_headers.copy()
        headers['User-Agent'] = self.ua.random
        
        # إضافة headers عشوائية إضافية
        additional_headers = [
            ('DNT', '1'),
            ('Sec-GPC', '1'),
        ]
        
        for header, value in random.sample(additional_headers, k=random.randint(0, 1)):
            headers[header] = value
        
        # التأكد من عدم طلب Brotli
        headers['Accept-Encoding'] = 'gzip, deflate'
            
        return headers
    
    @staticmethod
    def is_pinterest_url(url: str) -> bool:
        """
        فحص متقدم لروابط Pinterest
        
        Args:
            url: الرابط المراد فحصه
            
        Returns:
            True إذا كان رابط Pinterest صالح
        """
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip().lower()
        
        # أنماط Pinterest المحدثة
        pinterest_patterns = [
            r'(https?://)?(www\.)?pinterest\.com/pin/[\w-]+',
            r'(https?://)?(www\.)?pin\.it/[\w-]+',
            r'(https?://)?pinterest\.com/.*',
            r'(https?://)?.*\.pinterest\.com/.*',
            r'(https?://)?(br|ar|fr|de|es|it|ru)\.pinterest\.com/.*'
        ]
        
        for pattern in pinterest_patterns:
            if re.search(pattern, url):
                return True
        
        return 'pinterest' in url and ('pin' in url or '/idea' in url)
    
    def _extract_pin_id(self, url: str) -> Optional[str]:
        """
        استخراج معرف Pin من الرابط
        
        Args:
            url: رابط Pinterest
            
        Returns:
            معرف Pin أو None
        """
        # أنماط استخراج Pin ID
        patterns = [
            r'/pin/(\d+)',
            r'pin\.it/([a-zA-Z0-9]+)',
            r'pinterest\.com/pin/(\d+)',
            r'/pin/([a-zA-Z0-9]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def _expand_short_url(self, url: str) -> str:
        """
        توسيع الروابط المختصرة
        
        Args:
            url: الرابط المختصر
            
        Returns:
            الرابط الكامل
        """
        try:
            if 'pin.it' in url:
                headers = self._get_fresh_headers()
                
                async with self.session.head(url, headers=headers, allow_redirects=True) as response:
                    return str(response.url)
        except Exception as e:
            logger.warning(f"فشل توسيع الرابط: {str(e)}")
        
        return url
    
    async def _get_pin_data_from_page(self, url: str) -> Optional[Dict[str, Any]]:
        """
        استخراج بيانات Pin من صفحة الويب مباشرة
        
        Args:
            url: رابط Pin
            
        Returns:
            بيانات Pin أو None
        """
        try:
            headers = self._get_fresh_headers()
            
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"فشل تحميل الصفحة: {response.status}")
                    return None
                
                html_content = await response.text()
                
                # البحث عن JSON data في الصفحة
                json_patterns = [
                    r'<script[^>]*>\s*window\.__PWS_DATA__\s*=\s*({.*?});\s*</script>',
                    r'<script[^>]*>\s*window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>',
                    r'"__PWS_DATA__":\s*({.*?}),',
                    r'"resourceDataCache":\s*({.*?}),',
                ]
                
                for pattern in json_patterns:
                    matches = re.findall(pattern, html_content, re.DOTALL)
                    for match in matches:
                        try:
                            data = json.loads(match)
                            
                            # البحث عن بيانات الفيديو في البيانات المستخرجة
                            video_data = self._extract_video_from_data(data)
                            if video_data:
                                return video_data
                                
                        except json.JSONDecodeError:
                            continue
                
                # طريقة بديلة: البحث عن روابط الفيديو مباشرة في HTML
                video_patterns = [
                    r'"video_list":\s*\{[^}]*"V_HLSV4":\s*\{[^}]*"url":\s*"([^"]+)"',
                    r'"videos":\s*\{[^}]*"video_list":\s*\{[^}]*"V_HLSV3":\s*\{[^}]*"url":\s*"([^"]+)"',
                    r'"story_pin_data_id":[^}]*"video_url":\s*"([^"]+)"',
                    r'contentUrl":\s*"([^"]*\.mp4[^"]*)"',
                    r'"video":\s*\{[^}]*"url":\s*"([^"]+\.mp4[^"]*)"',
                ]
                
                for pattern in video_patterns:
                    matches = re.findall(pattern, html_content)
                    if matches:
                        video_url = matches[0].replace('\\/', '/')
                        if video_url.startswith('http'):
                            # استخراج العنوان والوصف من الصفحة
                            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content)
                            title = title_match.group(1) if title_match else "Pinterest Video"
                            title = title.replace(' | Pinterest', '').strip()
                            
                            description_match = re.search(r'"description":\s*"([^"]*)"', html_content)
                            description = description_match.group(1) if description_match else ""
                            
                            return {
                                'video_url': video_url,
                                'title': title,
                                'description': description,
                                'thumbnail': self._extract_thumbnail_from_html(html_content)
                            }
                
                logger.warning("لم يتم العثور على بيانات فيديو في الصفحة")
                return None
                
        except Exception as e:
            logger.error(f"خطأ في استخراج بيانات Pin: {str(e)}")
            return None
    
    def _extract_video_from_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        استخراج معلومات الفيديو من البيانات المهيكلة
        
        Args:
            data: البيانات المستخرجة من الصفحة
            
        Returns:
            معلومات الفيديو أو None
        """
        try:
            # البحث في مسارات مختلفة للبيانات
            search_paths = [
                ['props', 'initialReduxState', 'pins'],
                ['props', 'pageProps', 'pin'],
                ['resourceDataCache'],
                ['pins'],
                ['pin']
            ]
            
            for path in search_paths:
                current_data = data
                for key in path:
                    if isinstance(current_data, dict) and key in current_data:
                        current_data = current_data[key]
                    else:
                        break
                else:
                    # تم العثور على البيانات، البحث عن الفيديو
                    video_info = self._find_video_in_structure(current_data)
                    if video_info:
                        return video_info
            
            return None
            
        except Exception as e:
            logger.warning(f"خطأ في استخراج الفيديو من البيانات: {str(e)}")
            return None
    
    def _find_video_in_structure(self, data: Any) -> Optional[Dict[str, Any]]:
        """
        البحث عن معلومات الفيديو في هيكل البيانات
        
        Args:
            data: البيانات للبحث فيها
            
        Returns:
            معلومات الفيديو أو None
        """
        if isinstance(data, dict):
            # البحث عن مفاتيح الفيديو المعروفة
            video_keys = ['video_list', 'videos', 'story_pin_data', 'video_url']
            
            for key in video_keys:
                if key in data:
                    video_data = data[key]
                    
                    if key == 'video_list' and isinstance(video_data, dict):
                        # تجربة أنواع جودة مختلفة
                        quality_keys = ['V_HLSV4', 'V_HLSV3', 'V_HLSV3_WEB', 'V_HLSV3_MOBILE']
                        for quality_key in quality_keys:
                            if quality_key in video_data and 'url' in video_data[quality_key]:
                                url = video_data[quality_key]['url']
                                if url:
                                    return {
                                        'video_url': url,
                                        'title': data.get('title', data.get('grid_title', 'Pinterest Video')),
                                        'description': data.get('description', ''),
                                        'thumbnail': data.get('images', {}).get('orig', {}).get('url', ''),
                                        'quality': quality_key
                                    }
                    
                    elif key == 'video_url' and isinstance(video_data, str):
                        return {
                            'video_url': video_data,
                            'title': data.get('title', 'Pinterest Video'),
                            'description': data.get('description', ''),
                            'thumbnail': data.get('thumbnail', '')
                        }
            
            # البحث المتكرر في البيانات المتداخلة
            for value in data.values():
                result = self._find_video_in_structure(value)
                if result:
                    return result
        
        elif isinstance(data, list):
            for item in data:
                result = self._find_video_in_structure(item)
                if result:
                    return result
        
        return None
    
    def _extract_thumbnail_from_html(self, html_content: str) -> str:
        """
        استخراج رابط الصورة المصغرة من HTML
        
        Args:
            html_content: محتوى HTML
            
        Returns:
            رابط الصورة المصغرة
        """
        thumbnail_patterns = [
            r'"images":\s*\{[^}]*"orig":\s*\{[^}]*"url":\s*"([^"]+)"',
            r'property="og:image"\s+content="([^"]+)"',
            r'"thumbnail":\s*"([^"]+)"',
        ]
        
        for pattern in thumbnail_patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(1).replace('\\/', '/')
        
        return ""
    
    async def _download_video_file(self, video_url: str, pin_id: str) -> Optional[str]:
        """
        تحميل ملف الفيديو من الرابط المباشر
        
        Args:
            video_url: رابط الفيديو المباشر
            pin_id: معرف Pin
            
        Returns:
            مسار الملف المحمل أو None
        """
        try:
            headers = self._get_fresh_headers()
            headers['Referer'] = 'https://www.pinterest.com/'
            
            # تحديد امتداد الملف
            file_extension = 'mp4'
            if '.webm' in video_url:
                file_extension = 'webm'
            elif '.mov' in video_url:
                file_extension = 'mov'
            
            filename = f"pinterest_{pin_id}_{int(time.time())}.{file_extension}"
            filepath = self.download_dir / filename
            
            logger.info(f"بدء تحميل الفيديو: {video_url}")
            
            async with self.session.get(video_url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"فشل تحميل الفيديو: {response.status}")
                    return None
                
                total_size = int(response.headers.get('content-length', 0))
                
                async with aiofiles.open(filepath, 'wb') as file:
                    downloaded = 0
                    async for chunk in response.content.iter_chunked(8192):
                        await file.write(chunk)
                        downloaded += len(chunk)
                        
                        # تسجيل التقدم كل MB
                        if downloaded % (1024 * 1024) == 0:
                            progress = (downloaded / total_size * 100) if total_size > 0 else 0
                            logger.info(f"تقدم التحميل: {progress:.1f}%")
            
            file_size = filepath.stat().st_size
            if file_size < 1024:  # أقل من 1KB
                logger.error(f"الملف المحمل صغير جداً: {file_size} bytes")
                filepath.unlink()
                return None
            
            logger.info(f"تم تحميل الفيديو بنجاح: {filepath} ({file_size / (1024*1024):.2f} MB)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"خطأ في تحميل الفيديو: {str(e)}")
            return None
    
    async def download_video(self, url: str) -> Optional[Dict[str, Any]]:
        """
        تحميل فيديو Pinterest بالنظام المتقدم
        
        Args:
            url: رابط Pinterest
            
        Returns:
            معلومات الفيديو المحمل أو None
        """
        if not self.is_pinterest_url(url):
            logger.error(f"الرابط ليس من Pinterest: {url}")
            return None
        
        try:
            # توسيع الروابط المختصرة
            if 'pin.it' in url:
                url = await self._expand_short_url(url)
            
            # استخراج معرف Pin
            pin_id = self._extract_pin_id(url)
            if not pin_id:
                logger.error(f"فشل استخراج معرف Pin: {url}")
                return None
            
            logger.info(f"بدء تحميل Pin: {pin_id}")
            
            # إضافة تأخير عشوائي لتجنب الحظر
            await asyncio.sleep(random.uniform(1, 3))
            
            # استخراج بيانات الفيديو من الصفحة
            video_data = await self._get_pin_data_from_page(url)
            if not video_data:
                logger.error("فشل استخراج بيانات الفيديو")
                return None
            
            video_url = video_data.get('video_url')
            if not video_url:
                logger.error("لم يتم العثور على رابط الفيديو")
                return None
            
            # تحميل الفيديو
            filepath = await self._download_video_file(video_url, pin_id)
            if not filepath:
                return None
            
            return {
                'filepath': filepath,
                'title': video_data.get('title', 'Pinterest Video'),
                'description': video_data.get('description', ''),
                'thumbnail': video_data.get('thumbnail', ''),
                'pin_id': pin_id,
                'video_url': video_url,
                'filesize': Path(filepath).stat().st_size
            }
            
        except Exception as e:
            logger.error(f"خطأ في تحميل الفيديو: {str(e)}")
            return None
    
    async def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """
        الحصول على معلومات الفيديو دون تحميله
        
        Args:
            url: رابط Pinterest
            
        Returns:
            معلومات الفيديو أو None
        """
        if not self.is_pinterest_url(url):
            return None
        
        try:
            if 'pin.it' in url:
                url = await self._expand_short_url(url)
            
            pin_id = self._extract_pin_id(url)
            if not pin_id:
                return None
            
            video_data = await self._get_pin_data_from_page(url)
            if video_data:
                return {
                    'title': video_data.get('title', 'Pinterest Video'),
                    'description': video_data.get('description', ''),
                    'thumbnail': video_data.get('thumbnail', ''),
                    'pin_id': pin_id,
                    'has_video': bool(video_data.get('video_url'))
                }
            
            return None
            
        except Exception as e:
            logger.error(f"خطأ في الحصول على معلومات الفيديو: {str(e)}")
            return None
    
    def cleanup_file(self, filepath: str) -> None:
        """حذف ملف بعد الاستخدام"""
        try:
            path = Path(filepath)
            if path.exists():
                path.unlink()
                logger.info(f"تم حذف الملف: {filepath}")
        except Exception as e:
            logger.error(f"خطأ في حذف الملف: {str(e)}")
    
    def cleanup_old_files(self, max_age_hours: int = 2) -> None:
        """حذف الملفات القديمة"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            deleted_count = 0
            
            for filepath in self.download_dir.iterdir():
                if filepath.is_file():
                    file_age = current_time - filepath.stat().st_mtime
                    if file_age > max_age_seconds:
                        filepath.unlink()
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"تم حذف {deleted_count} ملف قديم")
                        
        except Exception as e:
            logger.error(f"خطأ في تنظيف الملفات: {str(e)}")


# كلاس wrapper للتوافق مع الكود الحالي
class PinterestDownloader:
    """كلاس للتوافق مع الكود الحالي"""
    
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = download_dir
        self.advanced_downloader = AdvancedPinterestDownloader(download_dir)
        logger.info("تم تهيئة النظام المتقدم للتحميل")
    
    @staticmethod
    def is_pinterest_url(url: str) -> bool:
        return AdvancedPinterestDownloader.is_pinterest_url(url)
    
    async def download_video(self, url: str) -> Optional[Dict[str, Any]]:
        async with self.advanced_downloader as downloader:
            return await downloader.download_video(url)
    
    async def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        async with self.advanced_downloader as downloader:
            return await downloader.get_video_info(url)
    
    def cleanup_file(self, filepath: str) -> None:
        self.advanced_downloader.cleanup_file(filepath)
    
    def cleanup_old_files(self, max_age_hours: int = 2) -> None:
        self.advanced_downloader.cleanup_old_files(max_age_hours)
