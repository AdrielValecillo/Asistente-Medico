from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Leer la URL de la base de datos desde las variables de entorno
DATABASE_URL = os.getenv("DATABASE_URL")

# Verificar que la variable de entorno DATABASE_URL esté definida
if not DATABASE_URL:
    raise ValueError("La variable de entorno DATABASE_URL no está configurada.")

# Asegurarse de que la URL especifica el driver psycopg para evitar ambigüedades
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Crear el motor de la base de datos
engine = create_engine(DATABASE_URL)

# Crear una clase de sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crear una clase base para los modelos declarativos
Base = declarative_base()

# Función para obtener una sesión de la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 