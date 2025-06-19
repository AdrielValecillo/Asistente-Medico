import os
import tempfile
from dotenv import load_dotenv

# --- Dependencias de FastAPI ---
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# --- Dependencias de LangChain ---
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader # <-- Cargador de PDFs
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_postgres.vectorstores import PGVector # <-- ¡El nuevo Vector Store!
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN INICIAL
# -----------------------------------------------------------------------------
load_dotenv()

# Validaciones de variables de entorno
if not os.getenv("GOOGLE_API_KEY"):
    raise Exception("La variable de entorno GOOGLE_API_KEY no está configurada.")
if not os.getenv("DATABASE_URL"):
    raise Exception("La variable de entorno DATABASE_URL no está configurada.")

app = FastAPI(
    title="API de RAG con PDF y Supabase",
    description="Sube un PDF y hazle preguntas usando RAG con Gemini y pgvector.",
    version="2.0.0",
)

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# 2. LÓGICA DEL RAG (AHORA CONECTADO A SUPABASE)
# -----------------------------------------------------------------------------

# El nombre de la colección (tabla) en nuestra base de datos vectorial
COLLECTION_NAME = "grados_uni"

# Modelo de Embeddings
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

# URL de conexión a la base de datos (leída desde .env)
connection = os.getenv("DATABASE_URL")

# Inicializamos el Vector Store conectándonos a nuestra tabla existente.
# Usamos PGVector.from_existing_index para esto.
vector_store = PGVector.from_existing_index(
    embedding=embeddings,                   # El modelo de embeddings que usamos
    collection_name=COLLECTION_NAME,        # El nombre de nuestra tabla/colección
    connection=connection,                  # La URL de conexión (parámetro corregido)
    pre_delete_collection=False,            # MUY IMPORTANTE: para no borrar la tabla al iniciar
    async_mode=True
)

def setup_rag_chain():
    """
    Configura la cadena de RAG. Ahora es más simple:
    - Ya no carga archivos locales, solo se conecta al Vector Store.
    """
    # a. Modelo LLM (Gemini)
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.5)

    # b. Retriever (obtenido directamente de nuestro Vector Store persistente)
    retriever = vector_store.as_retriever()

    # c. Prompt Template
    prompt = ChatPromptTemplate.from_template("""
    Eres un asistente experto y solo respondes basándote en el contexto proporcionado.
    Si la respuesta no se encuentra en el contexto, di "No tengo información suficiente para responder a esa pregunta".
    No inventes información.

    Contexto:
    {context}

    Pregunta:
    {input}

    Respuesta:
    """)
    
    # d. Cadenas de LangChain
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    
    return rag_chain

# Creamos la cadena una sola vez al iniciar la aplicación
rag_chain = setup_rag_chain()


# -----------------------------------------------------------------------------
# 3. DEFINICIÓN DE LA API (Endpoints)
# -----------------------------------------------------------------------------

class PreguntaRequest(BaseModel):
    pregunta: str

@app.get("/", summary="Endpoint raíz de bienvenida")
def read_root():
    return {"mensaje": "API de RAG funcionando. Usa /docs para interactuar."}

# --- ¡NUEVO ENDPOINT PARA SUBIR PDFs! ---
@app.post("/subir-pdf", summary="Carga y procesa un archivo PDF")
async def subir_pdf(file: UploadFile = File(...)):
    """
    Este endpoint recibe un archivo PDF, lo procesa y lo almacena en la base de datos vectorial.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF.")

    # Usamos un archivo temporal para guardar el PDF y que PyPDFLoader pueda leerlo
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # 1. Cargar el PDF
        loader = PyPDFLoader(tmp_path)
        docs = loader.load()

        # 2. Dividir el texto en chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = text_splitter.split_documents(docs)

        # 3. Añadir los chunks a la base de datos vectorial
        # PGVector se encargará de crear los embeddings y guardarlos
        vector_store.add_documents(splits)

    except Exception as e:
        # Si algo sale mal, lanzamos un error HTTP
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {e}")
    finally:
        # Nos aseguramos de borrar el archivo temporal
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)
    
    return {"mensaje": f"Archivo '{file.filename}' procesado y añadido a la base de conocimiento."}


@app.post("/preguntar", summary="Realiza una pregunta al sistema RAG")
async def preguntar(request: PreguntaRequest):
    """
    Recibe una pregunta y la responde usando la información de los PDFs cargados.
    """
    try:
        response = await rag_chain.ainvoke({"input": request.pregunta})
        return {"respuesta": response["answer"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar la pregunta: {e}")