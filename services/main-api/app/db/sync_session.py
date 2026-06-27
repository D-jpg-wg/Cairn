from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import setting

# Синхронный движок к ТОЙ ЖЕ БД, что и async-движок, но через psycopg2.
# Нужен воркеру Celery: его задачи синхронные

sync_engine = create_engine(setting.sync_db_url, pool_pre_ping=True)

SyncSession = sessionmaker(bind=sync_engine, expire_on_commit=False)

with SyncSession() as session:
    session.commit()
