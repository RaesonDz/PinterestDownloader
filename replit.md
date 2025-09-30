# Pinterest Video Downloader Telegram Bot

## Overview

This is a Telegram bot that downloads Pinterest videos on demand. The bot features mandatory channel subscription enforcement, video caching to avoid redundant downloads, and persistent user tracking. Users send Pinterest links, and the bot downloads and delivers the videos directly through Telegram.

## User Preferences

Preferred communication style: Simple, everyday language (Arabic).

## Recent Changes

**2025-09-30 (Update 2)**: إضافة نظام الإدارة والتحكم الديناميكي
- تم إضافة جدول BotSettings لتخزين إعدادات البوت بشكل ديناميكي
- تم إضافة نظام المسؤول (Admin) مع استثناء من الاشتراك الإجباري
- تم إضافة لوحة تحكم /admin مع إحصائيات مفصلة
- تم إضافة إمكانية تغيير معرف القناة بشكل ديناميكي عبر أمر /setchannel
- معرف المسؤول (TELEGRAM_ADMIN_ID) يتم تخزينه في Secrets

**2025-09-30 (Initial)**: إنشاء مشروع جديد لبوت تلجرام لتحميل فيديوهات Pinterest
- تم إنشاء البوت بمعايير احترافية باستخدام Python 3.11+
- تم إضافة جميع الميزات المطلوبة: الاشتراك الإجباري، قاعدة البيانات، معالجة الأخطاء
- البوت قيد التشغيل ويستجيب للأوامر والرسائل بنجاح

## System Architecture

### Core Components

**1. Bot Framework (bot.py)**
- Built on `python-telegram-bot` library (v21.4) for Telegram API interaction
- Implements handler-based architecture for processing commands, messages, and callback queries
- Enforces mandatory channel subscription (`@Garren_Store`) before allowing downloads
- Uses async/await pattern for non-blocking operations

**2. Video Downloader (downloader.py)**
- Uses `yt-dlp` as the primary video extraction engine
- Validates Pinterest URLs using regex pattern matching (supports `pinterest.com` and `pin.it` domains)
- Implements local file system storage in `downloads/` directory
- Returns video metadata (title, duration, file path) after successful downloads

**3. Database Layer (database.py)**
- Uses SQLModel ORM with SQLite as the database engine
- Three primary data models:
  - **User**: Tracks user_id, username, subscription status, and activity timestamps
  - **DownloadedVideo**: Caches video metadata and Telegram file_id for reuse
  - **BotSettings**: Stores dynamic bot configuration (channel_id, channel_username, etc.)
- File-based storage (`pinterest_bot.db`) for persistence
- Implements download count tracking to monitor popular content
- Supports dynamic configuration changes without code modifications

### Design Patterns

**Subscription Gate Pattern**
- Problem: Ensure users subscribe to a specific channel before using the bot
- Solution: Check channel membership before processing download requests
- Implementation: Store required channel ID (`-1002353060403`) and handle subscription verification via callback queries

**Video Caching Strategy**
- Problem: Avoid re-downloading the same Pinterest videos multiple times
- Solution: Store Telegram `file_id` after first upload, reuse for subsequent requests
- Benefits: Reduces bandwidth usage, faster delivery, less load on Pinterest servers
- Trade-off: Requires database storage for URL-to-file_id mapping

**Async Download Processing**
- Problem: Video downloads can be time-consuming and block bot responses
- Solution: Use asyncio with yt-dlp for non-blocking download operations
- Benefits: Bot remains responsive during downloads, can handle multiple concurrent requests

### Data Flow

1. User sends Pinterest URL → URL validation
2. Check user subscription status in database
3. If not subscribed → Display subscription prompt with inline keyboard
4. If subscribed → Check if video already downloaded (cache lookup)
5. Cache hit → Reuse existing Telegram file_id
6. Cache miss → Download with yt-dlp → Upload to Telegram → Store file_id
7. Update user activity timestamp and download statistics

## External Dependencies

### Third-Party Services
- **Telegram Bot API**: Primary interface for user interaction
- **Pinterest**: Source platform for video content (indirect, via yt-dlp)

### Key Libraries
- **python-telegram-bot (v21.4)**: Telegram bot framework with async support
- **yt-dlp**: Universal video downloader, handles Pinterest video extraction
- **SQLModel**: ORM layer combining SQLAlchemy and Pydantic for type-safe database operations
- **httpx**: Modern async HTTP client (likely used by yt-dlp or telegram library)
- **aiofiles**: Async file I/O operations for handling downloaded videos

### Database
- **SQLite**: Embedded relational database
- No external database server required
- File-based storage at `pinterest_bot.db`
- Suitable for single-instance deployment

### File System
- Local storage directory: `downloads/`
- Stores temporary video files before Telegram upload
- May require cleanup mechanism for disk space management