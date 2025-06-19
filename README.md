# Asistente Médico Inteligente: Análisis de Reportes con IA

## 1. Resumen del Proyecto

El **Asistente Médico Inteligente** es una aplicación web diseñada para ayudar a pacientes a comprender y gestionar sus resultados de exámenes médicos. La plataforma permite a los usuarios subir sus informes en formato PDF, recibir un análisis y resumen detallado generado por Inteligencia Artificial, y mantener un historial clínico consolidado.

El objetivo principal es empoderar a los pacientes, dándoles una herramienta para "traducir" la terminología médica compleja a un lenguaje comprensible, identificar tendencias en su salud a lo largo del tiempo y tener toda su información médica organizada y accesible en un solo lugar.

---

## 2. Características Principales

- **Gestión de Usuarios por Cédula:** Sistema de identificación simple y efectivo donde cada usuario accede a su perfil e historial a través de su número de cédula.
- **Análisis de Reportes PDF:** Sube cualquier informe médico en formato PDF y la IA se encarga de extraer, procesar y analizar el texto.
- **Resúmenes Potenciados por IA:** Para cada documento subido, el sistema genera un resumen claro, destacando los hallazgos más importantes, valores fuera de rango y posibles implicaciones.
- **Historial Clínico Digital:** Todos los reportes analizados se guardan de forma segura y se asocian al perfil del usuario, creando un historial clínico digital.
- **Informe General Consolidado:** La aplicación puede analizar el historial completo de un usuario para generar un **informe general**, identificando patrones, tendencias y cambios en la salud del paciente a lo largo del tiempo.
- **Interfaz Intuitiva y Fluida:** La interfaz está diseñada para ser fácil de usar, con una experiencia de usuario que permite navegar, subir archivos y ver resultados de forma rápida y sin recargar la página.
- **Gestión de Informes:** Los usuarios pueden eliminar informes individuales de su historial si así lo desean.

---

## 3. Arquitectura y Tecnologías Utilizadas

La aplicación sigue una arquitectura moderna, separando claramente las responsabilidades del backend, el frontend y el servicio de inteligencia artificial.

### Backend

- **Framework:** **FastAPI**, un framework de Python de alto rendimiento, ideal para construir APIs rápidas y asíncronas.
- **Base de Datos Relacional:** **PostgreSQL**, utilizado para almacenar la información de los usuarios y los metadatos de los reportes.
- **ORM:** **SQLAlchemy**, para interactuar de forma segura y eficiente con la base de datos PostgreSQL.
- **Migraciones:** **Alembic** se utiliza para gestionar y versionar los cambios en el esquema de la base de datos.

### Frontend

- **Motor de Plantillas:** **Jinja2**, para renderizar el HTML dinámicamente desde el backend de FastAPI.
- **JavaScript (Vanilla):** Se utiliza JavaScript puro para manipular el DOM, gestionar la interactividad del usuario y realizar llamadas asíncronas (Fetch API) a los endpoints del backend, creando una experiencia de usuario de "Single-Page Application" (SPA) sin necesidad de recargar la página.
- **Framework CSS:** **Bootstrap 5**, para un diseño responsive, moderno y limpio, utilizando componentes como modales, tarjetas y botones.

### Inteligencia Artificial y Modelo de Lenguaje

El corazón de la aplicación es su capacidad para entender documentos médicos. Esto se logra mediante una arquitectura de **Retrieval-Augmented Generation (RAG)**.

- **Proveedor de Modelos:** **Google Generative AI (Gemini)**.
- **Framework de Orquestación:** **LangChain**, una librería que facilita la conexión y encadenamiento de todos los componentes del sistema RAG.
- **Modelos Utilizados:**
  - **Modelo de Embeddings:** `models/embedding-001` para convertir el texto de los documentos en vectores numéricos.
  - **Modelo de Lenguaje (LLM):** `gemini-1.5-flash` para la generación de resúmenes y respuestas.
- **Base de Datos Vectorial:** **PGVector**, una extensión de PostgreSQL que permite almacenar y realizar búsquedas de similitud semántica sobre los vectores (embeddings) de manera ultra-rápida.

#### ¿Cómo funciona el proceso RAG?

El sistema evita que la IA "invente" información, forzándola a basarse únicamente en los documentos del usuario.

1.  **Carga y División (Ingestión):**
    - Al subir un PDF, `PyPDFLoader` extrae el texto.
    - `RecursiveCharacterTextSplitter` divide el texto en fragmentos (chunks) más pequeños y manejables.

2.  **Embedding y Almacenamiento:**
    - Cada chunk de texto se convierte en un vector numérico (embedding) usando el modelo de Google.
    - Estos vectores se almacenan en la base de datos **PGVector**. **Crucialmente, se guardan en una "colección" cuyo nombre es único para cada usuario (ej: `user_123_reports`)**, garantizando la total privacidad y aislamiento de los datos.

3.  **Recuperación (Retrieval):**
    - Cuando se solicita un informe general, el sistema convierte la pregunta ("genera un informe consolidado") en un vector.
    - Luego, busca en la colección del usuario en PGVector los N chunks de texto cuyos vectores son más similares semánticamente a la pregunta.

4.  **Generación Aumentada (Generation):**
    - Los chunks recuperados (el contexto) se inyectan en un *prompt* junto con la pregunta original.
    - Este prompt enriquecido se envía al modelo `gemini-2.0-flash`, con la instrucción de "actuar como un médico y generar un informe basado **exclusivamente** en el contexto proporcionado".
    - El resultado es una respuesta coherente, precisa y fundamentada únicamente en los documentos del propio usuario.

---

## 4. Estructura del Proyecto

```
/
├── alembic/              # Scripts de migración de la base de datos
├── app/
│   ├── api/              # Lógica de la API (actualmente utils contiene lógica de IA)
│   ├── db/               # Configuración de la base de datos, modelos y esquemas
│   │   ├── models/       # Modelos de SQLAlchemy (tablas)
│   │   └── schemas/      # Esquemas de Pydantic (validación de datos)
│   ├── services/         # (Vacío, para futura lógica de negocio)
│   ├── templates/        # Archivos HTML de Jinja2 para el frontend
│   ├── __init__.py
│   ├── crud.py           # Funciones de Lógica de la BD (Crear, Leer, Actualizar, Borrar)
│   ├── main.py           # Archivo principal de FastAPI (define todos los endpoints)
│   └── rag_service.py    # Lógica del pipeline RAG y la IA
├── requirements.txt      # Dependencias de Python
└── README.md             # Este archivo
```

---

## 5. Guía de Instalación y Puesta en Marcha

Para ejecutar el proyecto en un entorno local, sigue estos pasos:

1.  **Clonar el Repositorio:**
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd <NOMBRE_DEL_DIRECTORIO>
    ```

2.  **Crear un Entorno Virtual:**
    ```bash
    python -m venv env
    source env/bin/activate  # En Windows: env\Scripts\activate
    ```

3.  **Instalar Dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar Variables de Entorno:**
    Crea un archivo llamado `.env` en la raíz del proyecto y añade las siguientes variables:
    ```
    # URL de conexión a tu base de datos PostgreSQL con la extensión PGVector activada
    DATABASE_URL="postgresql+psycopg://usuario:contraseña@host:puerto/basedatos"

    # Tu clave de API de Google Generative AI (obtenida de Google AI Studio)
    GEMINI_API_KEY="TU_API_KEY_DE_GEMINI"
    ```
    *Nota: El driver `psycopg` se usa para operaciones síncronas y `asyncpg` (instalado vía requirements) se usa internamente para las asíncronas.*

5.  **Ejecutar las Migraciones (si es la primera vez):**
    Asegúrate de que la base de datos esté creada y luego ejecuta:
    ```bash
    alembic upgrade head
    ```

6.  **Iniciar el Servidor:**
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```
    La aplicación estará disponible en `http://127.0.0.1:8000`. La opción `--reload` reiniciará el servidor automáticamente cada vez que hagas un cambio en el código. 
