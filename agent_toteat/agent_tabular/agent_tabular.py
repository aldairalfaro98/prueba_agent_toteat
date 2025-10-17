from google.adk.agents import LlmAgent
from google.genai import types
from . import prompt_tabular
from ..tools.tool_tabular import tabular_insights as tool_tabular
from dotenv import load_dotenv
import os
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
Model = "gemini-2.5-flash"  # "gemini-2.5-pro"  # "gemini-2.5-flash"
temperature = 0.4

#───────────────────────────────────────────────────────────────
# Definición del agente raíz
# ───────────────────────────────────────────────────────────────
agent_tabular = LlmAgent (
    name="agent_tablas",
    model=Model,
    description="Agente especializado en manejar y analizar datos tabulares, un csv el cual proporcionara informacón estructurada, sobre información de ordenes de restarantes.",
    instruction= prompt_tabular.instrucciones_tabular,

    generate_content_config=types.GenerateContentConfig
    (
        temperature= temperature,
    ),

    tools=
    [
        tool_tabular,
    ],
)


