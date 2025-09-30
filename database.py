"""
قاعدة البيانات لتخزين معلومات المستخدمين والروابط المحملة
"""
import logging
from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, SQLModel, create_engine, Session, select

logger = logging.getLogger(__name__)


class User(SQLModel, table=True):
    """نموذج المستخدم في قاعدة البيانات"""
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(unique=True, index=True)
    username: Optional[str] = None
    first_name: Optional[str] = None
    is_subscribed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)


class DownloadedVideo(SQLModel, table=True):
    """نموذج الفيديوهات المحملة"""
    __tablename__ = "downloaded_videos"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(unique=True, index=True)
    file_id: str
    title: Optional[str] = None
    duration: Optional[int] = None
    downloaded_at: datetime = Field(default_factory=datetime.utcnow)
    download_count: int = Field(default=1)


class BotSettings(SQLModel, table=True):
    """نموذج إعدادات البوت"""
    __tablename__ = "bot_settings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Database:
    """كلاس لإدارة قاعدة البيانات"""
    
    def __init__(self, db_path: str = "pinterest_bot.db"):
        """
        تهيئة قاعدة البيانات
        
        Args:
            db_path: مسار ملف قاعدة البيانات
        """
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        self._create_tables()
        logger.info(f"تم تهيئة قاعدة البيانات: {db_path}")
    
    def _create_tables(self) -> None:
        """إنشاء جداول قاعدة البيانات"""
        SQLModel.metadata.create_all(self.engine)
    
    def add_user(
        self, 
        user_id: int, 
        username: Optional[str] = None, 
        first_name: Optional[str] = None
    ) -> User:
        """
        إضافة مستخدم جديد أو تحديث معلوماته
        
        Args:
            user_id: معرف المستخدم في تلجرام
            username: اسم المستخدم
            first_name: الاسم الأول
            
        Returns:
            كائن المستخدم
        """
        with Session(self.engine) as session:
            statement = select(User).where(User.user_id == user_id)
            user = session.exec(statement).first()
            
            if user:
                user.username = username
                user.first_name = first_name
                user.last_activity = datetime.utcnow()
            else:
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name
                )
                session.add(user)
            
            session.commit()
            session.refresh(user)
            logger.info(f"تم إضافة/تحديث المستخدم: {user_id}")
            return user
    
    def get_user(self, user_id: int) -> Optional[User]:
        """
        الحصول على معلومات المستخدم
        
        Args:
            user_id: معرف المستخدم
            
        Returns:
            كائن المستخدم أو None
        """
        with Session(self.engine) as session:
            statement = select(User).where(User.user_id == user_id)
            return session.exec(statement).first()
    
    def update_subscription_status(self, user_id: int, is_subscribed: bool) -> None:
        """
        تحديث حالة اشتراك المستخدم
        
        Args:
            user_id: معرف المستخدم
            is_subscribed: حالة الاشتراك
        """
        with Session(self.engine) as session:
            statement = select(User).where(User.user_id == user_id)
            user = session.exec(statement).first()
            
            if user:
                user.is_subscribed = is_subscribed
                session.commit()
                logger.info(f"تم تحديث حالة الاشتراك للمستخدم {user_id}: {is_subscribed}")
    
    def add_downloaded_video(
        self, 
        url: str, 
        file_id: str, 
        title: Optional[str] = None,
        duration: Optional[int] = None
    ) -> DownloadedVideo:
        """
        إضافة فيديو محمل إلى قاعدة البيانات
        
        Args:
            url: رابط الفيديو
            file_id: معرف الملف في تلجرام
            title: عنوان الفيديو
            duration: مدة الفيديو بالثواني
            
        Returns:
            كائن الفيديو المحمل
        """
        with Session(self.engine) as session:
            statement = select(DownloadedVideo).where(DownloadedVideo.url == url)
            video = session.exec(statement).first()
            
            if video:
                video.download_count += 1
                logger.info(f"الفيديو موجود مسبقاً، تم زيادة عداد التحميل: {url}")
            else:
                video = DownloadedVideo(
                    url=url,
                    file_id=file_id,
                    title=title,
                    duration=duration
                )
                session.add(video)
                logger.info(f"تم إضافة فيديو جديد: {url}")
            
            session.commit()
            session.refresh(video)
            return video
    
    def get_downloaded_video(self, url: str) -> Optional[DownloadedVideo]:
        """
        البحث عن فيديو محمل في قاعدة البيانات
        
        Args:
            url: رابط الفيديو
            
        Returns:
            كائن الفيديو أو None
        """
        with Session(self.engine) as session:
            statement = select(DownloadedVideo).where(DownloadedVideo.url == url)
            return session.exec(statement).first()
    
    def get_total_users(self) -> int:
        """الحصول على عدد المستخدمين الكلي"""
        with Session(self.engine) as session:
            statement = select(User)
            return len(session.exec(statement).all())
    
    def get_total_videos(self) -> int:
        """الحصول على عدد الفيديوهات المحملة"""
        with Session(self.engine) as session:
            statement = select(DownloadedVideo)
            return len(session.exec(statement).all())
    
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        الحصول على إعداد من قاعدة البيانات
        
        Args:
            key: مفتاح الإعداد
            default: القيمة الافتراضية إذا لم يتم العثور على الإعداد
            
        Returns:
            قيمة الإعداد أو القيمة الافتراضية
        """
        with Session(self.engine) as session:
            statement = select(BotSettings).where(BotSettings.key == key)
            setting = session.exec(statement).first()
            return setting.value if setting else default
    
    def set_setting(self, key: str, value: str) -> None:
        """
        تعيين إعداد في قاعدة البيانات
        
        Args:
            key: مفتاح الإعداد
            value: قيمة الإعداد
        """
        with Session(self.engine) as session:
            statement = select(BotSettings).where(BotSettings.key == key)
            setting = session.exec(statement).first()
            
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = BotSettings(key=key, value=value)
                session.add(setting)
            
            session.commit()
            logger.info(f"تم تحديث الإعداد: {key} = {value}")
