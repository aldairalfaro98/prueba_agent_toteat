from google.adk.agents import LlmAgent
from google.genai import types
from . import prompt_unstructured
from ..tools.tool_unstructured import tool_unstructured
from dotenv import load_dotenv
import os
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
Model = "gemini-2.5-flash"  # "gemini-2.5-pro"  # "gemini-2.5-flash"
temperature = 0.4

#───────────────────────────────────────────────────────────────
# Definición del agente raíz
# ───────────────────────────────────────────────────────────────
agent_unstructured = LlmAgent (
    name="agent_data",
    model=Model,
    description="Agente especializado en manejar y analizar datos no estructurados, como documentos de texto, DOCs o archivos PDF, para extraer información relevante y proporcionar respuestas precisas.",
    instruction= prompt_unstructured.instrucciones_unstructured,
    
    generate_content_config=types.GenerateContentConfig
    (
        temperature= temperature,
    ),
    tools=
    [
        tool_unstructured,
    ],
)
