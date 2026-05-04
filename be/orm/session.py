import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    f"?charset=utf8mb4"
)
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# SessionLocal produces a new DB session per request
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Base class for all ORM models
Base = declarative_base()


def get_db():
    # DB와 통신할 수 있는 새로운 세션 객체 생성
    db = SessionLocal()
    
    
    # return 대신 yield를 사용함으로서, 반환하자마자 함수가 멈춰버리는 것 방지
    # db를 사용해 작업을 수행한뒤 내부적으로 일시정지를 풀어 finally 실행
    try:
        yield db
    
    # try와 함께 사용되는 세트 중 하나, finally 아래에 있는 코드는 반드시 실행됨.
    finally:
        db.close()
