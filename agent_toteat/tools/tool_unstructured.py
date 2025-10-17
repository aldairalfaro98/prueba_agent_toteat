# tools/tabular/tool_unstructured.py
# =============================================================================
# Tool: unstructured_rag_tool
# Autor: Nair + ChatGPT
# Descripción:
#   Búsqueda semántica (RAG) sobre documentos locales (PDF, DOCX, MD).
#   Esta versión indexa TODOS los archivos al inicio (sin carga perezosa) para
#   evitar fallos de recuperación. Cachea el modelo en disco y la instancia en RAM,
#   y mantiene los embeddings de cada documento en memoria (con invalidación por
#   mtime+size si el archivo cambia).
#
# Contrato ADK:
#   - Callable: tool_unstructured(query: str, scope: str="auto", files: list[str]=None, top_k: int=None) -> dict
#   - Retorno JSON: {
#       "best_answer": str,
#       "low_confidence": bool,
#       "results": [{"source": str, "score": float, "snippet": str}],
#       "debug": {"indexed": [str], "skipped": [str], "timings_ms": {...}}
#     }
#
# Notas AFC (Automatic Function Calling):
#   - Evitar tipos con Union (p.ej. list[str] | None). Usamos tipos simples y
#     normalizamos internamente para compatibilidad.
# =============================================================================

from __future__ import annotations

import functools
import json
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence, Tuple, TypedDict

import numpy as np

# Dependencias opcionales (se validan al usarlas)
try:
    from docx import Document as _DocxDocument  # python-docx
except Exception:  # pragma: no cover
    _DocxDocument = None  # type: ignore

try:
    import PyPDF2  # type: ignore
except Exception:  # pragma: no cover
    PyPDF2 = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover
    SentenceTransformer = None  # type: ignore

# Cargar .env antes de leer variables
from dotenv import load_dotenv
load_dotenv()

# =============================================================================
# Configuración y defaults
# =============================================================================

# Cache del modelo en disco (estilo FAQS_bucket)
_DEFAULT_CACHE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "model_c")
)
MODEL_CACHE = os.getenv("SENTENCE_CACHE_DIR", _DEFAULT_CACHE_DIR)
os.makedirs(MODEL_CACHE, exist_ok=True)

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_DEBUG = os.getenv("UNSTRUCTURED_DEBUG", "false").lower() in {"1", "true", "yes"}

def _d(msg: str) -> None:
    if _DEBUG:
        print(f"[tool_unstructured] {msg}")

# Parámetros de ranking / confianza
TOP_K_DEFAULT = int(os.getenv("UNSTRUCTURED_TOP_K", "40"))
THRESHOLD = float(os.getenv("UNSTRUCTURED_THRESHOLD", "0.22"))
MIN_ACCEPTED = float(os.getenv("UNSTRUCTURED_MIN_ACCEPTED", "0.20"))

# Chunking por tipo (ajustables por .env)
MD_CHUNK_TOKENS = int(os.getenv("MD_CHUNK_TOKENS", "176"))
MD_OVERLAP_TOKENS = int(os.getenv("MD_OVERLAP_TOKENS", "80"))

DOCX_CHUNK_TOKENS = int(os.getenv("DOCX_CHUNK_TOKENS", "160"))
DOCX_OVERLAP_TOKENS = int(os.getenv("DOCX_OVERLAP_TOKENS", "64"))

PDF_CHUNK_TOKENS = int(os.getenv("PDF_CHUNK_TOKENS", "224"))
PDF_OVERLAP_TOKENS = int(os.getenv("PDF_OVERLAP_TOKENS", "96"))

# Corpus por .env (rutas relativas)
FILES_ENV = os.getenv("UNSTRUCTURED_FILES", "")
DEFAULT_FILES: List[str] = [p.strip() for p in FILES_ENV.split(",") if p.strip()]

# =============================================================================
# Tipos / modelos
# =============================================================================

Kind = Literal["md", "docx", "pdf"]

class DocumentRef(TypedDict):
    path: str
    kind: Kind

class Chunk(TypedDict):
    text: str
    meta: Dict[str, str]  # {path, locator, idx_local}

class IndexedDoc(TypedDict):
    etag: str
    kind: Kind
    chunks: List[Chunk]
    embeddings: np.ndarray  # shape: [n, dim]

class Result(TypedDict):
    source: str  # path#locator
    score: float
    snippet: str

# =============================================================================
# Extractores por tipo
# =============================================================================

class TextExtractor:
    kind: Kind
    def supports(self, kind: Kind) -> bool:
        return self.kind == kind

    def extract_text(self, path: Path) -> str:
        raise NotImplementedError

    def presection(self, text: str) -> List[str]:
        """Divide el texto en secciones antes de chunkear.
        Implementación por tipo:
          - MD: encabezados (##) y bloques
          - DOCX: párrafos/espacios
          - PDF: páginas
        """
        raise NotImplementedError

class MarkdownExtractor(TextExtractor):
    kind: Kind = "md"

    def extract_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def presection(self, text: str) -> List[str]:
        # Separar por encabezados ## o bloques largos
        blocks: List[str] = []
        current: List[str] = []
        for line in text.splitlines():
            if re.match(r"^##+\s+", line):
                if current:
                    blocks.append("\n".join(current).strip())
                    current = []
            current.append(line)
        if current:
            blocks.append("\n".join(current).strip())
        return [b for b in blocks if len(b.split()) > 5]

class DocxExtractor(TextExtractor):
    kind: Kind = "docx"

    def extract_text(self, path: Path) -> str:
        if _DocxDocument is None:
            raise RuntimeError("python-docx no está instalado")
        doc = _DocxDocument(str(path))
        paras = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n".join(paras)

    def presection(self, text: str) -> List[str]:
        # Seccionado simple por párrafos/espacios
        parts = re.split(r"\n{2,}", text)
        return [p.strip() for p in parts if len(p.split()) > 5]

class PdfExtractor(TextExtractor):
    kind: Kind = "pdf"

    def extract_text(self, path: Path) -> str:
        if PyPDF2 is None:
            raise RuntimeError("PyPDF2 no está instalado")
        reader = PyPDF2.PdfReader(str(path))
        out = []
        for i, page in enumerate(reader.pages):
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            out.append(f"[[PAGE {i+1}]]\n{txt.strip()}\n")
        return "\n".join(out)

    def presection(self, text: str) -> List[str]:
        parts = re.split(r"\[\[PAGE\s+\d+\]\]", text)
        return [p.strip() for p in parts if len(p.split()) > 5]

EXTRACTORS: List[TextExtractor] = [MarkdownExtractor(), DocxExtractor(), PdfExtractor()]

def _detect_kind(path: Path) -> Kind:
    ext = path.suffix.lower()
    if ext == ".md":
        return "md"
    if ext == ".docx":
        return "docx"
    if ext == ".pdf":
        return "pdf"
    raise ValueError(f"Formato no soportado: {path}")

# =============================================================================
# Chunker
# =============================================================================

@dataclass
class ChunkingConfig:
    tokens: int
    overlap: int

class Chunker:
    def __init__(self, cfg: ChunkingConfig) -> None:
        self.cfg = cfg

    def _split_section(self, section: str) -> List[str]:
        # Aproximación: 1 palabra ≈ 1 token
        words = re.findall(r"\S+", section)
        step = max(1, self.cfg.tokens - self.cfg.overlap)
        chunks: List[str] = []
        for start in range(0, len(words), step):
            piece = words[start : start + self.cfg.tokens]
            if not piece:
                break
            chunks.append(" ".join(piece))
        return chunks

    def chunk(self, sections: List[str], path: Path, kind: Kind) -> List[Chunk]:
        chunks: List[Chunk] = []
        for i, sec in enumerate(sections, start=1):
            pieces = self._split_section(sec)
            for j, piece in enumerate(pieces):
                locator = f"section-{i}"
                chunks.append(
                    Chunk(text=piece, meta={"path": str(path), "locator": locator, "idx_local": str(j)})
                )
        return chunks

# =============================================================================
# Embeddings (modelo + servicio)
# =============================================================================

@functools.lru_cache(maxsize=1)
def _load_model() -> "SentenceTransformer":  # type: ignore[name-defined]
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers no está instalado")
    _d("Cargando modelo SBERT (puede tardar la primera vez)…")
    return SentenceTransformer(MODEL_NAME, cache_folder=MODEL_CACHE)  # type: ignore

class EmbedderService:
    def __init__(self) -> None:
        self.model = _load_model()

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        embs = self.model.encode(list(texts), convert_to_numpy=True, show_progress_bar=False)
        return embs.astype(np.float32)

    def encode_query(self, q: str) -> np.ndarray:
        v = self.model.encode([q], convert_to_numpy=True, show_progress_bar=False)[0]
        return v.astype(np.float32)

# =============================================================================
# Índices en memoria (eager indexing)
# =============================================================================

class IndexStore:
    """
    Mantiene un índice por documento:
      - etag local (mtime+size)
      - lista de chunks
      - matriz de embeddings [n, dim]
    En esta versión, TODOS los documentos del .env se indexan al inicio.
    """
    def __init__(self, embedder: EmbedderService) -> None:
        self.embedder = embedder
        self.indices: Dict[str, IndexedDoc] = {}  # path -> IndexedDoc

    def _etag_local(self, path: Path) -> str:
        st = path.stat()
        return f"local-{int(st.st_mtime)}-{st.st_size}"

    def _chunk_cfg_for(self, kind: Kind) -> ChunkingConfig:
        if kind == "md":
            return ChunkingConfig(tokens=MD_CHUNK_TOKENS, overlap=MD_OVERLAP_TOKENS)
        if kind == "docx":
            return ChunkingConfig(tokens=DOCX_CHUNK_TOKENS, overlap=DOCX_OVERLAP_TOKENS)
        return ChunkingConfig(tokens=PDF_CHUNK_TOKENS, overlap=PDF_OVERLAP_TOKENS)

    def _extractor_for(self, kind: Kind) -> TextExtractor:
        ex = next((e for e in EXTRACTORS if e.supports(kind)), None)
        if ex is None:
            raise ValueError(f"Sin extractor para {kind}")
        return ex

    def ensure_indexed(self, doc: DocumentRef) -> IndexedDoc:
        """
        Indexa (o re-indexa si cambió el archivo) y devuelve el índice del documento.
        """
        path = Path(doc["path"]).resolve()
        if not path.exists():
            raise FileNotFoundError(str(path))
        etag = self._etag_local(path)

        hit = self.indices.get(str(path))
        if hit and hit["etag"] == etag:
            return hit

        # (re)indexar
        extractor = self._extractor_for(doc["kind"])
        raw = extractor.extract_text(path)
        sections = extractor.presection(raw)

        cfg = self._chunk_cfg_for(doc["kind"])
        chunks = Chunker(cfg).chunk(sections, path, doc["kind"])
        embeddings = self.embedder.encode_texts([c["text"] for c in chunks])

        idx: IndexedDoc = {"etag": etag, "kind": doc["kind"], "chunks": chunks, "embeddings": embeddings}
        self.indices[str(path)] = idx
        _d(f"Indexado {path.name}: {len(chunks)} chunks")
        return idx

    def ensure_all_indexed(self, files: List[str]) -> List[str]:
        """
        Indexa TODOS los documentos declarados en UNSTRUCTURED_FILES al iniciar.
        Devuelve la lista de paths indexados.
        """
        indexed: List[str] = []
        for f in files:
            p = Path(f)
            try:
                ref: DocumentRef = DocumentRef(path=str(p), kind=_detect_kind(p))  # type: ignore[arg-type]
                self.ensure_indexed(ref)
                indexed.append(str(p))
            except Exception as e:
                _d(f"Skip {p}: {e}")
        return indexed

# =============================================================================
# Búsqueda / Ranking
# =============================================================================

class QueryEngine:
    def __init__(self, store: IndexStore) -> None:
        self.store = store
        self.last_debug: Dict = {}

    def _cosine_sim(self, a: np.ndarray, B: np.ndarray) -> np.ndarray:
        a_norm = a / (np.linalg.norm(a) + 1e-8)
        B_norm = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-8)
        return B_norm @ a_norm

    def _route_candidates(self, query: str, scope: str, files: Optional[List[str]]) -> List[DocumentRef]:
        # Con indexación total, "auto" y "files" comparten casi todo,
        # pero "files" permite acotar el universo si el usuario lo desea.
        if scope == "files" and files:
            refs: List[DocumentRef] = []
            for f in files:
                p = Path(f)
                refs.append(DocumentRef(path=str(p), kind=_detect_kind(p)))  # type: ignore[arg-type]
            return refs

        # "auto": usar todos los del .env
        refs: List[DocumentRef] = []
        for f in DEFAULT_FILES:
            p = Path(f)
            refs.append(DocumentRef(path=str(p), kind=_detect_kind(p)))  # type: ignore[arg-type]
        return refs

    def search(self, query: str, scope: str, files: Optional[List[str]], top_k: int) -> Tuple[List[Result], bool, Dict]:
        t0 = time.time()
        qv = self.store.embedder.encode_query(query)

        candidates = self._route_candidates(query, scope, files)

        # Asegurar que todos los candidatos están indexados (por si hubo cambios en disco)
        indexed_docs: List[str] = []
        skipped_docs: List[str] = []
        rows: List[Result] = []

        for doc in candidates:
            try:
                idx = self.store.ensure_indexed(doc)
                sims = self._cosine_sim(qv, idx["embeddings"])  # [n]
                # En indexación global, tomamos N candidatos por documento para diversidad
                k_local = max(3, min(len(sims), max(5, int(math.ceil(top_k / max(1, len(candidates))) * 2))))
                top_idx = np.argsort(-sims)[:k_local]
                for ti in top_idx:
                    ch = idx["chunks"][int(ti)]
                    rows.append(Result(
                        source=f"{ch['meta']['path']}#{ch['meta']['locator']}",
                        score=float(sims[int(ti)]),
                        snippet=ch["text"],
                    ))
                indexed_docs.append(doc["path"])  # type: ignore[index]
            except Exception as e:
                skipped_docs.append(f"{doc['path']}: {e}")  # type: ignore[index]

        # Ranking global
        rows.sort(key=lambda r: r["score"], reverse=True)
        fused = rows[: top_k]
        max_score = fused[0]["score"] if fused else 0.0
        low_conf = bool(max_score < MIN_ACCEPTED)

        t1 = time.time()
        debug = {
            "indexed": indexed_docs,
            "skipped": skipped_docs,
            "timings_ms": {"total_ms": int((t1 - t0) * 1000)},
        }
        self.last_debug = debug
        return fused, low_conf, debug

    def compose_answer(self, ranked: List[Result]) -> str:
        if not ranked:
            return "No encontré suficiente contexto en los documentos locales para responder con confianza."
        # Tomar 2–4 pasajes top (compacto) para dar más cobertura
        parts: List[str] = []
        seen_sources = set()
        for r in ranked:
            if r["source"] in seen_sources:
                continue
            seen_sources.add(r["source"])
            s = r["snippet"].strip()
            if len(s) > 600:
                s = s[:600].rsplit(" ", 1)[0] + "…"
            parts.append(s)
            if len(parts) >= 4:
                break
        return "\n\n".join(parts)

# =============================================================================
# ToolAdapter (punto de entrada)
# =============================================================================

class ToolAdapter:
    def __init__(self) -> None:
        # Cargar modelo (cache en disco + instancia en RAM)
        self.embedder = EmbedderService()

        # Construir índice y EAGER INDEX de todos los archivos del .env
        self.store = IndexStore(self.embedder)
        self._ensure_defaults_exist()
        self._all_indexed = self.store.ensure_all_indexed(DEFAULT_FILES)
        _d(f"Preindexados: {len(self._all_indexed)} documentos")

        # Motor de consulta
        self.engine = QueryEngine(self.store)

        # Warmup opcional adicional (no necesario, ya cargamos arriba)
        if os.getenv("UNSTRUCTURED_WARMUP", "0") in {"1", "true", "yes"}:
            _ = self.embedder.model  # ya cargado por _load_model

    def _ensure_defaults_exist(self) -> None:
        missing = [f for f in DEFAULT_FILES if not Path(f).exists()]
        if missing:
            raise FileNotFoundError(
                "No se encontraron rutas declaradas en UNSTRUCTURED_FILES: " + ", ".join(missing)
            )

    def run(self, args: Dict) -> Dict:
        """
        Args esperados:
          - query: str (obligatorio)
          - scope: "auto" | "files" (opcional; default "auto")
          - files: [str] (opcional si scope="files")
          - top_k: int (opcional; default UNSTRUCTURED_TOP_K)
        """
        query = (args.get("query") or "").strip()
        if not query:
            raise ValueError("'query' es obligatorio")

        scope = args.get("scope") or "auto"
        files = args.get("files") or None
        top_k = int(args.get("top_k") or TOP_K_DEFAULT)

        ranked, low_conf, debug = self.engine.search(query, scope, files, top_k)
        best_answer = self.engine.compose_answer(ranked)

        return {
            "best_answer": best_answer,
            "low_confidence": low_conf,
            "results": ranked,
            "debug": debug,
        }

# =============================================================================
# CLI helper (opcional)
# =============================================================================

def run_tool(args_json: str) -> str:
    """
    Uso:
      python tools/tabular/tool_unstructured.py '{"query":"¿Cómo cierro una orden?"}'
    """
    adapter = ToolAdapter()
    args = json.loads(args_json)
    out = adapter.run(args)
    return json.dumps(out, ensure_ascii=False, indent=2)

if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) < 2:
        print("Uso: python tool_unstructured.py '{\"query\":\"...\"}'")
        raise SystemExit(1)
    print(run_tool(sys.argv[1]))

# =============================================================================
# Wrapper ADK (AFC-friendly)
# =============================================================================

_adapter_singleton = ToolAdapter()

def tool_unstructured(
    query: str,
    scope: str = "auto",
    files: list[str] = [],   # <- default compatible con list[str]
    top_k: int = 0           # <- default compatible con int
) -> dict:
    """
    Herramienta ADK: unstructured_rag_tool
    """
    # Normalización defensiva (sin mutar el default)
    if isinstance(files, str):
        files = [files]
    elif files is None:  # por si el modelo manda null
        files = []

    # 0 significa "usa el default interno"
    use_top_k = None if not top_k else int(top_k)

    args = {"query": query, "scope": scope}
    if files:
        args["files"] = files
    if use_top_k is not None:
        args["top_k"] = use_top_k

    return _adapter_singleton.run(args)

