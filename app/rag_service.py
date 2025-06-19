import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_postgres.vectorstores import PGVector
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
import logging
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

# --- Configuración y Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONNECTION_STRING = os.getenv("DATABASE_URL")
if not CONNECTION_STRING:
    raise ValueError("DATABASE_URL no está configurada.")

# Asegurarse de que la URL especifica el driver psycopg
if CONNECTION_STRING.startswith("postgresql://"):
    CONNECTION_STRING = CONNECTION_STRING.replace("postgresql://", "postgresql+psycopg://", 1)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY no está configurada.")

EMBEDDINGS = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GEMINI_API_KEY)
LLM = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7, google_api_key=GEMINI_API_KEY)

def get_vector_store_for_user(user_id: int) -> PGVector:
    """Obtiene o crea el vector store para un usuario específico."""
    collection_name = f"user_{user_id}_reports"
    
    store = PGVector(
        embeddings=EMBEDDINGS,
        collection_name=collection_name,
        connection=CONNECTION_STRING,
        use_jsonb=True # Recomendado para metadata
    )
    # PGVector en langchain-postgres ya no necesita el método 'create_collection' explícito.
    # La colección se crea al añadir los primeros documentos.
    return store

def add_pdf_to_vector_store_sync(user_id: int, file_path: str):
    """
    Procesa un PDF y lo añade al vector store del usuario.
    Esta función es síncrona y está diseñada para correr en un hilo separado.
    """
    try:
        collection_name = f"user_{user_id}_reports"
        logger.info(f"Iniciando procesamiento de PDF para el usuario {user_id} en la colección {collection_name}")

        # La inicialización del vector_store ahora ocurre dentro de esta función síncrona
        vector_store = PGVector(
            embeddings=EMBEDDINGS,
            collection_name=collection_name,
            connection=CONNECTION_STRING,
            use_jsonb=True,
        )

        # 1. Cargar el PDF de forma síncrona
        loader = PyPDFLoader(file_path)
        docs = loader.load()
        logger.info(f"PDF cargado, {len(docs)} páginas encontradas.")

        # 2. Dividir el texto en chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)
        logger.info(f"Documento dividido en {len(splits)} chunks.")

        # 3. Añadir los chunks a la base de datos vectorial (síncrono)
        vector_store.add_documents(splits)
        logger.info(f"Chunks añadidos exitosamente a la base de datos vectorial para el usuario {user_id}.")

    except Exception as e:
        logger.error(f"Error en add_pdf_to_vector_store_sync para el usuario {user_id}: {e}", exc_info=True)
        # Relanzamos la excepción para que el hilo principal se entere
        raise

async def generate_general_report(user_id: int):
    """Genera un informe general para un usuario basado en todos sus documentos."""
    try:
        collection_name = f"user_{user_id}_reports"
        
        # Para operaciones asíncronas, es necesario un engine asíncrono.
        async_engine = create_async_engine(CONNECTION_STRING)

        # Conectamos al vector store existente del usuario usando el engine asíncrono
        vector_store = PGVector(
            embeddings=EMBEDDINGS,
            collection_name=collection_name,
            connection=async_engine,
            use_jsonb=True,
        )
        
        # Comprobamos si la colección (y por tanto, la tabla) existe.
        # Una forma indirecta es intentar obtener el retriever y ver si hay documentos.
        # Langchain no ofrece un método 'exists()' directo y simple.
        
        retriever = vector_store.as_retriever(search_kwargs={'k': 15})

        prompt = ChatPromptTemplate.from_template("""
        Actúa como un médico experimentado que está revisando el historial completo de un paciente.
        Basándote EXCLUSIVAMENTE en el contexto proporcionado de sus diferentes informes médicos, elabora un informe general consolidado.

        Tu tarea es:
        1. Crear un resumen coherente de la condición general del paciente.
        2. Identificar y listar los hallazgos anormales o fuera de rango que se repiten a lo largo de los diferentes análisis.
        3. Señalar si existen tendencias notables (por ejemplo, un valor que ha ido subiendo o bajando con el tiempo).
        4. Ofrecer una conclusión general y recomendaciones basadas en el conjunto de los datos. No des consejos médicos que reemplacen una consulta.
        5. Si el contexto es insuficiente o no contiene informes médicos, indícalo claramente.

        Contexto de los informes del paciente:
        {context}

        Pregunta:
        {input}

        Informe General:
        """)

        question_answer_chain = create_stuff_documents_chain(LLM, prompt)
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)

        input_question = "Elabora un informe general consolidado basado en todos los documentos del historial."
        
        response = await rag_chain.ainvoke({"input": input_question})
        
        # Verificación extra: si la respuesta indica que no hay contexto, lanzamos un error.
        if "No tengo información suficiente" in response["answer"]:
             raise ValueError("No se encontraron suficientes datos en el historial para generar un informe.")

        return response["answer"]
    except ValueError as ve:
        # Capturamos el error de valor específico para dar un mensaje claro
        logger.warning(f"No se pudo generar el informe para el usuario {user_id}: {ve}")
        raise
    except Exception as e:
        logger.error(f"Error inesperado en generate_general_report para el usuario {user_id}: {e}", exc_info=True)
        raise 