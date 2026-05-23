# ==========================================
# BACKEND V2: INSTAGRAM SEARCH + АНАЛИЗ
# ==========================================
# Backend который ищет залетные рилсы и генерирует идеи на их основе
 
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
import os
import json
import logging
import asyncio
import anthropic
import aiohttp
import re
 
# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
# ===== БД =====
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./test.db')
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
 
# ===== МОДЕЛИ БД =====
 
class User(Base):
    """Пользователи"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    subscription_status = Column(String, default="free")
    subscription_ends = Column(DateTime, nullable=True)
 
class Profile(Base):
    """Профили аккаунтов"""
    __tablename__ = "profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String)
    niche = Column(String)
    audience = Column(String)
    voice = Column(String)
    fleshy = Column(String)  # Уникальная фишка
    profile_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
 
class IdeaHistory(Base):
    """История идей"""
    __tablename__ = "idea_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    profile_id = Column(Integer, index=True)
    idea = Column(JSON)
    generated_at = Column(DateTime, default=datetime.utcnow)
    saved = Column(Boolean, default=False)
 
# Создаём таблицы
Base.metadata.create_all(bind=engine)
 
# ===== PYDANTIC МОДЕЛИ =====
 
class ProfileCreateRequest(BaseModel):
    user_id: int
    profile_data: dict
 
# ===== FASTAPI ПРИЛОЖЕНИЕ =====
 
app = FastAPI(title="ReelsAI Backend V2")
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
 
# ===== HELPER ФУНКЦИИ =====
 
async def search_instagram_trending(niche: str) -> list:
    """
    Ищет залетные рилсы в Инстаграме по нише
    Использует web search чтобы найти популярные посты
    
    В реальности нужен Instagram API, но для MVP используем поиск
    """
    
    try:
        # Используем Anthropic web search
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # Создаём запрос для поиска
        search_prompt = f"""
Найди топ 5 самых залетных рилсов в нише "{niche}" на Инстаграме.
 
Для каждого рилса укажи:
1. Краткое описание (что происходит в видео)
2. Примерное количество просмотров (если можешь оценить)
3. Структура видео (как оно построено)
4. Главный хук (первые 0.5 секунды - что зацепит)
5. Какой звук/музыка
 
Ответ в JSON формате:
[
  {{
    "description": "...",
    "views": "100K+",
    "structure": "...",
    "hook": "...",
    "sound": "..."
  }}
]
        """
        
        message = client.messages.create(
            model="claude-opus-4-1-20250805",
            max_tokens=1500,
            messages=[
                {"role": "user", "content": search_prompt}
            ]
        )
        
        response_text = message.content[0].text
        
        # Парсим JSON
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            trending = json.loads(json_match.group())
            return trending
        
        return []
    
    except Exception as e:
        logger.error(f"Ошибка при поиске трендов: {e}")
        return []
 
async def analyze_and_generate_ideas(profile_data: dict, trending: list) -> list:
    """
    Анализирует залетные рилсы и генерирует идеи под конкретного пользователя
    
    1. Берёт залетные форматы
    2. Анализирует структуру
    3. Адаптирует под voice и фишку пользователя
    4. Генерирует новые идеи в его стиле
    """
    
    try:
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # Форматируем информацию о тренденах
        trending_text = json.dumps(trending, ensure_ascii=False, indent=2)
        
        # Создаём промпт для Claude
        prompt = f"""
Ты — эксперт по вирусному контенту в Instagram Reels.
 
ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:
• Ниша: {profile_data.get('niche', '')}
• Целевая аудитория: {profile_data.get('audience', '')}
• Tone of voice: {profile_data.get('voice', '')}
• Его фишка/уникальность: {profile_data.get('fleshy', '')}
• Название: {profile_data.get('name', '')}
 
ЗАЛЕТНЫЕ РИЛСЫ В ЕГО НИШЕ (ТО ЧТО РАБОТАЕТ СЕЙЧАС):
{trending_text}
 
ТВОЯ ЗАДАЧА:
1. Проанализируй почему эти рилсы залетают
2. Выдели рабочие форматы, хуки, структуры
3. АДАПТИРУЙ эти форматы под его стиль и фишку
4. Генерируй 3 НОВЫЕ идеи рилсов которые:
   - Используют доказанные форматы
   - Звучат как его контент (его voice)
   - Выделяют его уникальность (фишку)
   - Будут работать для его аудитории
 
ФОРМАТ ОТВЕТА (ТОЛЬКО JSON):
[
  {{
    "title": "Название идеи",
    "hook": "Точное описание первых 0.5 сек - что зацепит зрителя",
    "scenario": "Пошаговый сценарий как снимать (3-5 шагов)",
    "sound": "Конкретный звук/музыка/тип аудио",
    "why_viral": "Почему это работает конкретно в его нише",
    "views": "Ожидаемое количество просмотров",
    "hashtags": ["хэштег1", "хэштег2", "хэштег3", "хэштег4", "хэштег5"]
  }},
  ...
]
 
ВАЖНО:
- Идеи должны звучать как ОН БЫ ИХ ЗАПИСАЛ
- Не как "ИИ-идеи"
- На основе доказанных форматов
- Максимально адаптированы под его стиль
        """
        
        message = client.messages.create(
            model="claude-opus-4-1-20250805",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text
        
        # Парсим JSON
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            ideas = json.loads(json_match.group())
            return ideas
        
        return []
    
    except Exception as e:
        logger.error(f"Ошибка при генерации идей: {e}")
        return []
 
# ===== API ENDPOINTS =====
 
@app.get("/health")
async def health_check():
    """Проверка что сервер живой"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
 
@app.get("/user/{user_id}")
async def get_user(user_id: int):
    """Получить информацию о пользователе"""
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == user_id).first()
    db.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": user.id,
        "telegram_id": user.telegram_id,
        "subscription_status": user.subscription_status,
        "created_at": user.created_at.isoformat()
    }
 
@app.post("/profile/create")
async def create_profile(request: ProfileCreateRequest):
    """Создать новый профиль"""
    
    db = SessionLocal()
    
    try:
        # Создаём пользователя если не существует
        user = db.query(User).filter(User.telegram_id == request.user_id).first()
        if not user:
            user = User(telegram_id=request.user_id)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Создаём профиль
        profile = Profile(
            user_id=user.id,
            name=request.profile_data.get('name', ''),
            niche=request.profile_data.get('niche', ''),
            audience=request.profile_data.get('audience', ''),
            voice=request.profile_data.get('voice', ''),
            fleshy=request.profile_data.get('fleshy', ''),
            profile_data=request.profile_data
        )
        
        db.add(profile)
        db.commit()
        db.refresh(profile)
        
        return {
            "profile_id": profile.id,
            "message": "Profile created successfully",
            "status": 201
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        db.close()
 
@app.get("/ideas/generate")
async def generate_ideas(user_id: int, profile_id: int = None):
    """
    Генерировать идеи на основе актуальных трендов в Инстаграме
    
    1. Ищет залетные рилсы в нише пользователя
    2. Анализирует структуру
    3. Адаптирует под его стиль
    4. Выдаёт готовые идеи
    """
    
    db = SessionLocal()
    
    try:
        # Ищем пользователя
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Ищем профиль
        profile = None
        if profile_id:
            profile = db.query(Profile).filter(
                Profile.id == profile_id, 
                Profile.user_id == user.id
            ).first()
        else:
            profile = db.query(Profile).filter(
                Profile.user_id == user.id
            ).order_by(Profile.created_at.desc()).first()
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # ШАГ 1: Ищем залетные рилсы в его нише
        logger.info(f"Ищу тренды в нише: {profile.niche}")
        trending = await search_instagram_trending(profile.niche)
        
        if not trending:
            # Если не нашли - генерируем общие идеи
            logger.warning("Не удалось найти тренды, генерирую общие идеи")
            trending = [
                {"description": "Популярный формат в нише", "hook": "Интересный хук", "sound": "Популярный звук"}
            ]
        
        # ШАГ 2: Анализируем и адаптируем под пользователя
        logger.info(f"Генерирую идеи для профиля: {profile.name}")
        ideas = await analyze_and_generate_ideas(profile.profile_data, trending)
        
        # ШАГ 3: Сохраняем в историю
        for idea in ideas:
            idea_record = IdeaHistory(
                user_id=user.id,
                profile_id=profile.id,
                idea=idea
            )
            db.add(idea_record)
        
        db.commit()
        
        return {
            "ideas": ideas,
            "profile_id": profile.id,
            "niche": profile.niche,
            "message": "Ideas generated successfully"
        }
    
    except Exception as e:
        logger.error(f"Error generating ideas: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        db.close()
 
@app.get("/profiles/{user_id}")
async def get_user_profiles(user_id: int):
    """Получить все профили пользователя"""
    db = SessionLocal()
    
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        profiles = db.query(Profile).filter(Profile.user_id == user.id).all()
        
        return {
            "profiles": [
                {
                    "id": p.id,
                    "name": p.name,
                    "niche": p.niche,
                    "created_at": p.created_at.isoformat()
                }
                for p in profiles
            ]
        }
    
    finally:
        db.close()
 
@app.get("/subscription/{user_id}")
async def get_subscription_status(user_id: int):
    """Получить статус подписки"""
    db = SessionLocal()
    
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Проверяем не истекла ли подписка
        if user.subscription_ends and user.subscription_ends < datetime.utcnow():
            user.subscription_status = "free"
            db.commit()
        
        return {
            "status": user.subscription_status,
            "ends_at": user.subscription_ends.isoformat() if user.subscription_ends else None
        }
    
    finally:
        db.close()
