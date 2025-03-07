import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
import tkinter as tk
from tkinter import filedialog

load_dotenv()



def seleccionar_pdf():
    """Abre una ventana para seleccionar el archivo PDF"""
    root = tk.Tk()
    root.withdraw()
    archivo = filedialog.askopenfilename(
        title="Selecciona tu informe médico",
        filetypes=[("PDF files", "*.pdf"), ("Todos los archivos", "*.*")]
    )
    return archivo

def generate(file_upload):
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
    )

        # 1. Seleccionar y subir el PDF
    pdf_path = file_upload
    if not pdf_path:
        print("No se seleccionó ningún archivo")
        return
    
    if not os.path.exists(pdf_path):
        print(f"Error: El archivo {pdf_path} no existe")
        return

    try:
        uploaded_file = client.files.upload(file=pdf_path)
    except Exception as e:
        print(f"Error al subir el archivo: {str(e)}")
        return



    model = "gemini-2.0-flash-exp"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""Actúa como un médico especialista en análisis de laboratorio y ayuda a interpretar los resultados de los siguientes exámenes médicos que te voy a proporcionar. Si el archivo que se sube no contiene resultados médicos, por favor responde con un mensaje solicitando que se suba un documento válido. Si el archivo contiene resultados médicos, realiza las siguientes tareas:

Datos del Paciente:

Nombre:
Edad:
Género:
Historial médico relevante: [Ejemplo: diabetes tipo 2, hipertensión, etc.]
Medicamentos actuales:
Resultados del Examen:

[Incluir los resultados médicos obtenidos del PDF. Esto podría incluir análisis de sangre, radiografías, electrocardiogramas, etc.]
Ejemplo de resultados (con clasificación, referencia y valor):

Glucosa en sangre: 120 mg/dL (Elevado, referencia: 70-100 mg/dL)
Colesterol total: 240 mg/dL (Elevado, referencia: <200 mg/dL)
Frecuencia cardíaca: 80 latidos por minuto (Normal, referencia: 60-100 lpm)
Presión arterial: 140/90 mmHg (Elevado, referencia: 120/80 mmHg)
Explicación de los Resultados:

Explica cada resultado de manera sencilla, indicando si está dentro del rango normal o si es preocupante.
Explica qué significa cada término médico. Por ejemplo:
Glucosa en sangre: \"La glucosa en sangre es un indicador importante para evaluar el control de la diabetes. Un nivel de glucosa de 120 mg/dL es ligeramente elevado, lo que puede ser un signo de que los niveles de azúcar no están bien controlados. Es importante monitorear estos niveles y consultar a un médico si persiste.\"
Colesterol elevado: \"El colesterol elevado, como en este caso con 240 mg/dL, puede aumentar el riesgo de enfermedades cardiovasculares. Este tipo de colesterol alto puede bloquear las arterias y aumentar el riesgo de infartos o accidentes cerebrovasculares.\"
Recomendaciones Personalizadas:

Proporciona recomendaciones claras y prácticas basadas en los resultados.
Las recomendaciones deben estar orientadas a mejorar la salud del paciente de forma accesible, es decir, consejos que cualquier persona pueda seguir sin ser un experto médico.
Ejemplos:

Glucosa elevada: \"Te recomendaría seguir una dieta baja en carbohidratos simples (como pan blanco y refrescos) y aumentar la actividad física, como caminar 30 minutos al día. Esto puede ayudarte a controlar tus niveles de glucosa.\"
Colesterol elevado: \"Para el colesterol, intenta reducir el consumo de alimentos altos en grasas saturadas, como frituras y carnes rojas. Añadir alimentos ricos en fibra, como frutas y verduras, puede ayudar a reducir los niveles de colesterol.\"
Validación de Documento:

Si el archivo subido no contiene resultados médicos, responde con:
\"Por favor, sube un documento válido que contenga resultados médicos para poder proporcionar la interpretación y las recomendaciones correspondientes.\""""),
            ],
        ),
        types.Content(
            role="model",
            parts=[
                types.Part.from_text(text="""Entendido. Estoy listo para analizar los resultados de laboratorio que me proporciones. Por favor, sube el documento con los resultados.

Una vez que lo subas, lo analizaré y te proporcionaré lo siguiente:

1.  **Datos del Paciente:** (Si los puedo extraer del documento o me los proporcionas tú)
    *   Nombre
    *   Edad
    *   Género
    *   Historial médico relevante
    *   Medicamentos actuales

2.  **Resultados del Examen:** Extraeré los resultados relevantes del documento y los presentaré de forma clara.

3.  **Explicación de los Resultados:** Explicaré cada resultado, indicando si está dentro del rango normal y, en caso contrario, qué significa y por qué es preocupante.  Definiré los términos médicos relevantes.

4.  **Recomendaciones Personalizadas:** Basándome en los resultados, te daré recomendaciones prácticas y accesibles para mejorar tu salud.

**Si el documento no contiene resultados médicos, te indicaré que subas un documento válido.**

Es importante recordar que esta interpretación es informativa y no sustituye una consulta médica profesional.  Siempre debes discutir los resultados y las recomendaciones con tu médico tratante.

Espero tu documento.
"""),
            ],
        ),
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(
                    file_uri=uploaded_file.uri,
                    mime_type=uploaded_file.mime_type,
                ),
                types.Part.from_text(text="""examen"""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        response_mime_type="text/plain",
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config
    )

    return response.text 
