from fastapi import FastAPI, Request, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import tempfile
import os
from app.api.utils.ia import generate
import html
import re
import uuid

# Instancia de FastAPI
app = FastAPI()

# Temporary storage for results (key: unique ID, value: result data)
results_store = {}

# Configuración de Jinja2 para las plantillas
templates = Jinja2Templates(directory="app/templates")

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

# Ruta para procesar el archivo PDF
@app.post("/medical-report/")
async def medical_report(file: UploadFile = File(...)):
    # Validar tipo de archivo
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    
    tmp_path = None
    try:
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
            
        result_2 = generate(tmp_path)
        result_1 = formatear_mensaje(result_2)
        result = quitar_asteriscos(result_1)
        
        # Generate unique ID and store result
        result_id = str(uuid.uuid4())
        results_store[result_id] = result
        
        os.unlink(tmp_path)
        
        # Return redirect URL with ID
        return JSONResponse({"redirect_url": f"/resultados/{result_id}"})
        
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail="Error al procesar el archivo")

# New route to fetch results by ID
@app.get("/resultados/{result_id}")
async def resultados(request: Request, result_id: str):
    if result_id not in results_store:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    resultado = results_store[result_id]
    return templates.TemplateResponse("resultados.html", {
        "request": request,
        "resultado": resultado
    })




@app.get("/ping")
def ping():
    return {"status": "ok"}