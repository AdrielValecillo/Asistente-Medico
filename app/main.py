from fastapi import FastAPI, Request, File, UploadFile, HTTPException, Depends, Body
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import tempfile
import os
from app.api.utils.ia import generate
import html
import re
import uuid
import hashlib
import asyncio

from . import crud, rag_service
from .db import database, schemas
from .db.models import models

models.Base.metadata.create_all(bind=database.engine)

# Instancia de FastAPI
app = FastAPI()

# Temporary storage for results (key: unique ID, value: result data)
results_store = {}

# Configuración de Jinja2 para las plantillas
templates = Jinja2Templates(directory="app/templates")

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def formatear_mensaje(mensaje: str) -> str:
    # Escapa caracteres especiales
    mensaje_escapado = html.escape(mensaje)
    # Reemplaza doble asteriscos (**texto**) por <strong>texto</strong>
    mensaje_destacado = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', mensaje_escapado)
    # Reemplaza líneas que empiecen con "* " por viñetas
    # (ej.: "* elemento" -> "• elemento")
    mensaje_con_vinetas = re.sub(r'^\*\s+(.*)$', r'• \1', mensaje_destacado, flags=re.MULTILINE)
    # Reemplaza saltos de línea con <br>
    mensaje_formateado = mensaje_con_vinetas.replace("\n", "<br>")
    return mensaje_formateado

def quitar_asteriscos(mensaje: str) -> str:
    return mensaje.replace("*", "•")

# Ruta para la página principal
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/check-user/")
async def check_user(cedula: str = Body(..., embed=True), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_cedula(db, cedula=cedula)
    if db_user:
        return {"exists": True, "user": {"full_name": db_user.full_name, "cedula": db_user.cedula}}
    return {"exists": False}

@app.post("/get-reports/")
async def get_reports(cedula: str = Body(..., embed=True), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_cedula(db, cedula=cedula)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    reports = crud.get_reports_by_user_id(db, user_id=db_user.id)
    return reports

@app.post("/generate-general-report/", summary="Genera un informe consolidado para un usuario")
async def generate_report_endpoint(cedula: str = Body(..., embed=True), db: Session = Depends(get_db)):
    db_user = crud.get_user_by_cedula(db, cedula=cedula)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        general_report_raw = await rag_service.generate_general_report(db_user.id)
        general_report_formatted = formatear_mensaje(general_report_raw)
        return {"report": general_report_formatted}
    except Exception as e:
        # Podríamos tener un log aquí
        raise HTTPException(status_code=500, detail=f"No se pudo generar el informe general: {str(e)}")

@app.post("/delete-report/")
async def delete_report(report_id: int = Body(..., embed=True), db: Session = Depends(get_db)):
    success = crud.delete_report_by_id(db, report_id=report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return {"status": "ok"}

@app.post("/register-user/")
async def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_cedula(db, cedula=user.cedula)
    if db_user:
        raise HTTPException(status_code=400, detail="Cédula ya registrada")
    new_user = crud.create_user(db=db, user=user)
    return new_user

# Ruta para procesar el archivo PDF
@app.post("/medical-report/")
async def medical_report(file: UploadFile = File(...), cedula: str = Body(...), db: Session = Depends(get_db)):
    # Validar tipo de archivo
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    
    db_user = crud.get_user_by_cedula(db, cedula=cedula)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    tmp_path = None
    try:
        content = await file.read()
        # Calcular hash del archivo
        file_hash = hashlib.sha256(content).hexdigest()

        # Verificar si el archivo ya fue subido por este usuario
        existing_report = crud.get_report_by_hash_for_user(db, user_id=db_user.id, file_hash=file_hash)
        if existing_report:
            raise HTTPException(status_code=400, detail="Este archivo ya ha sido analizado anteriormente.")

        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # --- AÑADIR PDF AL VECTOR STORE (MODO ROBUSTO) ---
        # Ejecuta la función síncrona de procesamiento de archivos en un hilo separado
        # para no bloquear el servidor.
        await asyncio.to_thread(
            rag_service.add_pdf_to_vector_store_sync, 
            user_id=db_user.id, 
            file_path=tmp_path
        )
            
        result_2 = generate(tmp_path)

        # Verificar si la IA determinó que no es un examen médico
        invalid_doc_message = "Por favor, sube un documento válido"
        if result_2.strip().startswith(invalid_doc_message):
            os.unlink(tmp_path) # Limpiar el archivo temporal
            raise HTTPException(status_code=400, detail="El archivo subido no parece ser un examen médico. Por favor, intente con otro documento.")

        result_1 = formatear_mensaje(result_2)
        result = quitar_asteriscos(result_1)
        
        # Guardar el reporte en la base de datos
        db_report = crud.create_report_for_user(
            db=db, 
            report=schemas.ReportCreate(report_content=result), 
            user_id=db_user.id,
            file_hash=file_hash
        )

        os.unlink(tmp_path)
        
        # Return redirect URL with report ID
        return JSONResponse({"redirect_url": f"/resultados/{db_report.id}"})
        
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail="Error al procesar el archivo")

# New route to fetch results by ID
@app.get("/resultados/{report_id}")
async def resultados(request: Request, report_id: int, db: Session = Depends(get_db)):
    db_report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if db_report is None:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    
    return templates.TemplateResponse("resultados.html", {
        "request": request,
        "resultado": db_report.report_content,
        "user_cedula": db_report.user.cedula
    })

@app.get("/ping")
def ping():
    return {"status": "ok"}