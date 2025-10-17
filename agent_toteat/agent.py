# ───────────────────────────────────────────────────────────────
# Imports del ADK
# ───────────────────────────────────────────────────────────────
from google.adk.agents import LlmAgent
from google.genai import types
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.adk.tools.agent_tool import AgentTool
import asyncio

#───────────────────────────────────────────────────────────────
# Importar sub-agentes
# ───────────────────────────────────────────────────────────────
from .agent_tabular.agent_tabular import agent_tabular
from .agent_unstructured.agent_unstrucutred import agent_unstructured

#───────────────────────────────────────────────────────────────
# Importar herramientas
# ───────────────────────────────────────────────────────────────
#from google.adk.tools import google_search

#───────────────────────────────────────────────────────────────
# Importar prompts
# ───────────────────────────────────────────────────────────────
from . import prompt_orquestador

#───────────────────────────────────────────────────────────────
# Configuración del modelo y autenticación
# ───────────────────────────────────────────────────────────────
from dotenv import load_dotenv
import os
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
Model = "gemini-2.5-flash"  # "gemini-2.5-pro"  # "gemini-2.5-flash"
temperature = 0.4

#───────────────────────────────────────────────────────────────
# Definición del agente raíz
# ───────────────────────────────────────────────────────────────
root_agent = LlmAgent (
    name = "agent_orquestador",
    model = Model,
    description="Agente orquestador que gestiona sub-agentes para poder responder solicitudes del usuario.",
    instruction= prompt_orquestador.instrucciones_orquestador,

    generate_content_config=types.GenerateContentConfig
    (
        temperature= temperature,
    ),
    
    tools=[
        AgentTool(agent=agent_tabular),        # <-- agente como tool
        AgentTool(agent=agent_unstructured),   # <-- agente como tool
    ],
)



# ───────────────────────────────────────────────────────────────
# Helper para ejecutar con sesión (pruebas locales / adk web)
# ───────────────────────────────────────────────────────────────

APP_NAME = "app_toteat"  # nombre lógico de la app/sesión
_session_service = InMemorySessionService()

def run_with_session(session_id: str, user_message: str) -> str:
    """Ejecuta una interacción dentro de una sesión (modo local/dev)."""

    async def _ensure_session():
        await _session_service.create_session(
            app_name=APP_NAME,
            user_id=session_id,
            session_id=session_id,
        )

    # Crea la sesión de forma sincrónica (bloquea hasta terminar)
    asyncio.run(_ensure_session())

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=_session_service,
    )

    content = types.Content(role="user", parts=[types.Part(text=user_message)])
    events = runner.run(
        user_id=session_id,
        session_id=session_id,
        new_message=content,
    )

    last_text = ""
    for ev in events or []:
        c = getattr(ev, "content", None)
        if isinstance(c, str) and c.strip():
            last_text = c
            continue
        if c and getattr(c, "parts", None):
            for p in c.parts:
                if getattr(p, "text", None):
                    last_text = p.text
    return last_text
