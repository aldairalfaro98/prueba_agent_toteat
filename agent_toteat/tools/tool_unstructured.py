"""
Tool: unstructured_rag_tool
Author: Nair + ChatGPT (spec-driven)

Resumen
-------
Tool RAG para documentos locales mixtos (PDF, DOCX, MD), optimizado para:
- Carga perezosa por documento
- Cache dual del modelo SBERT (disco + RAM)
- Cache de embeddings por archivo (RAM) con invalidación por mtime+size
- Ranking por documento y fusión global
- Contrato JSON estable.

Arquitectura interna
--------------
- TextExtractor (interfaz) + implementaciones por tipo: Markdown, DOCX, PDF
- Chunker: segmentación por tokens aproximados con solapamiento
- EmbedderService (singleton): SentenceTransformers con cache
- IndexStore: índices en RAM por documento (embeddings + chunks) + MRU
- QueryEngine: rutear candidatos, buscar, fusionar y aplicar umbrales
- ToolAdapter: valida args y empaqueta la salida para el ADK

Variables de entorno (.env)
--------------------------------------
UNSTRUCTURED_FILES           lista coma-separada de rutas relativas
SENTENCE_CACHE_DIR           carpeta para cache HF (opcional)
UNSTRUCTURED_TOP_K           default 8
UNSTRUCTURED_THRESHOLD       default 0.20
UNSTRUCTURED_MIN_ACCEPTED    default 0.18
UNSTRUCTURED_DEBUG           true/false (default false)
MD_CHUNK_TOKENS, MD_OVERLAP_TOKENS, DOCX_*, PDF_*    (opcionales)
UNSTRUCTURED_MAX_DOCS        límite MRU en memoria (default 5)

Uso de la herramienta
-------------
args: {
  "query": str,
  "scope": "auto" | "files" (opcional, default "auto"),
  "files": [str] (opcional si scope="files"),
  "top_k": int (opcional)
}

Salida JSON:
{
  "best_answer": str,
  "low_confidence": bool,
  "results": [{"source": str, "score": float, "snippet": str}],
  "debug": {"indexed": [str], "skipped": [str], "timings_ms": {...}}
}
"""
from __future__ import annotations

import dataclasses
import functools
import io
import json
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Tuple, TypedDict

import numpy as np

# Dependencias suaves (solo se importan si se usan)
try:
    from docx import Document as _DocxDocument  # python-docx
except Exception:  # pragma: no cover - import diferido
    _DocxDocument = None  # type: ignore

try:
    import PyPDF2  # type: ignore
except Exception:  # pragma: no cover
    PyPDF2 = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover
    SentenceTransformer = None  # type: ignore


# ==========================
# Utilidades generales
# ==========================

_DEBUG = os.getenv("UNSTRUCTURED_DEBUG", "false").lower() in {"1", "true", "yes"}


def _d(msg: str) -> None:
    if _DEBUG:
        print(f"[unstructured_rag_tool] {msg}")


# Carga de envs con defaults sensatos
TOP_K_DEFAULT = int(os.getenv("UNSTRUCTURED_TOP_K", "8"))
THRESHOLD = float(os.getenv("UNSTRUCTURED_THRESHOLD", "0.20"))
MIN_ACCEPTED = float(os.getenv("UNSTRUCTURED_MIN_ACCEPTED", "0.18"))
MAX_DOCS = int(os.getenv("UNSTRUCTURED_MAX_DOCS", "5"))  # MRU cap (Plan B descartará 2)

# Chunking tunable por tipo
MD_CHUNK_TOKENS = int(os.getenv("MD_CHUNK_TOKENS", "176"))
MD_OVERLAP_TOKENS = int(os.getenv("MD_OVERLAP_TOKENS", "56"))
DOCX_CHUNK_TOKENS = int(os.getenv("DOCX_CHUNK_TOKENS", "144"))
DOCX_OVERLAP_TOKENS = int(os.getenv("DOCX_OVERLAP_TOKENS", "40"))
PDF_CHUNK_TOKENS = int(os.getenv("PDF_CHUNK_TOKENS", "208"))
PDF_OVERLAP_TOKENS = int(os.getenv("PDF_OVERLAP_TOKENS", "64"))

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_CACHE = os.getenv("SENTENCE_CACHE_DIR")  # si None, usa la default de HF

# Lista de archivos del corpus (rutas relativas)
FILES_ENV = os.getenv("UNSTRUCTURED_FILES", "")
DEFAULT_FILES: List[str] = [p.strip() for p in FILES_ENV.split(",") if p.strip()]


# ==========================
# Tipos
# ==========================
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


# ==========================
# Extractores
# ==========================
class TextExtractor:
    kind: Kind

    def supports(self, kind: Kind) -> bool:
        return self.kind == kind

    def extract_text(self, path: Path) -> str:
        raise NotImplementedError

    def presection(self, text: str) -> List[str]:
        """Divide el texto en secciones mayores antes del chunking.
        Implementaciones por tipo (MD: encabezados, DOCX: párrafos/secciones,
        PDF: páginas)."""
        raise NotImplementedError


class MarkdownExtractor(TextExtractor):
    kind: Kind = "md"

    def extract_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def presection(self, text: str) -> List[str]:
        # Dividir por encabezados ## o líneas en blanco múltiples
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
        # Limpieza: descartar bloques muy pequeños
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
        # Secciones por subtítulos (líneas en MAYÚSCULAS o seguidas de dos saltos)
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
        # Dividir por páginas marcadas
        parts = re.split(r"\[\[PAGE\s+\d+\]\]", text)
        return [p.strip() for p in parts if len(p.split()) > 5]


EXTRACTORS: List[TextExtractor] = [MarkdownExtractor(), DocxExtractor(), PdfExtractor()]


def _detect_kind(path: Path) -> Kind:
    ext = path.suffix.lower()
    if ext in {".md"}:
        return "md"
    if ext in {".docx"}:
        return "docx"
    if ext in {".pdf"}:
        return "pdf"
    raise ValueError(f"Formato no soportado: {path}")


# ==========================
# Chunker
# ==========================


def _approx_token_len(text: str) -> int:
    """Aproximación simple a nº de tokens.
    (palabras + signos) ~ funciona bien para cortes por tamaño.
    """
    # Separar por espacios y puntuación básica
    return max(1, len(re.findall(r"\w+|[^\w\s]", text)))


@dataclass
class ChunkingConfig:
    tokens: int
    overlap: int


class Chunker:
    def __init__(self, cfg: ChunkingConfig) -> None:
        self.cfg = cfg

    def _split_section(self, section: str) -> List[str]:
        # Divide una sección en chunks aproximados por tokens
        words = re.findall(r"\S+", section)
        # Heurística: 1 palabra ~ 1 token aprox.
        step = self.cfg.tokens - self.cfg.overlap
        if step <= 0:
            step = max(1, self.cfg.tokens // 2)
        chunks: List[str] = []
        for start in range(0, len(words), step):
            piece = words[start : start + self.cfg.tokens]
            if not piece:
                break
            chunks.append(" ".join(piece))
        return chunks

    def chunk(self, sections: List[str], path: Path, kind: Kind) -> List[Chunk]:
        chunks: List[Chunk] = []
        for idx, sec in enumerate(sections):
            for j, piece in enumerate(self._split_section(sec)):
                locator = f"section-{idx+1}"
                if kind == "pdf":
                    # Si el texto venía de páginas, intentar detectar el marcador [[PAGE n]]
                    # (ya fue removido en presection); el locator por sección está bien
                    pass
                chunks.append(Chunk(text=piece, meta={"path": str(path), "locator": locator, "idx_local": str(j)}))
        return chunks


# ==========================
# Embeddings
# ==========================


@functools.lru_cache(maxsize=1)
def _load_model() -> "SentenceTransformer":  # type: ignore[name-defined]
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers no está instalado")
    _d("Cargando modelo SBERT (puede tardar la primera vez)…")
    model = SentenceTransformer(MODEL_NAME, cache_folder=MODEL_CACHE)  # type: ignore
    return model


class EmbedderService:
    def __init__(self) -> None:
        self.model = _load_model()

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        embs = self.model.encode(list(texts), convert_to_numpy=True, show_progress_bar=False)
        return embs.astype(np.float32)

    def encode_query(self, q: str) -> np.ndarray:
        v = self.model.encode([q], convert_to_numpy=True, show_progress_bar=False)[0]
        return v.astype(np.float32)


# ==========================
# IndexStore (RAM + MRU)
# ==========================


class IndexStore:
    def __init__(self, embedder: EmbedderService) -> None:
        self.embedder = embedder
        self.indices: Dict[str, IndexedDoc] = {}
        self.mru: List[str] = []  # paths ordenados por uso reciente

    def _etag_local(self, path: Path) -> str:
        st = path.stat()
        return f"local-{int(st.st_mtime)}-{st.st_size}"

    def _ensure_capacity(self) -> None:
        if len(self.mru) <= MAX_DOCS:
            return
        # Plan B: descartar los 2 menos recientes
        to_drop = max(0, len(self.mru) - MAX_DOCS + 2)
        for _ in range(to_drop):
            victim = self.mru.pop(0)
            self.indices.pop(victim, None)
            _d(f"MRU: descartado {victim}")

    def ensure_indexed(self, doc: DocumentRef) -> IndexedDoc:
        path = Path(doc["path"]).resolve()
        if not path.exists():
            raise FileNotFoundError(str(path))
        etag = self._etag_local(path)

        hit = self.indices.get(str(path))
        if hit and hit["etag"] == etag:
            # actualizar MRU
            if str(path) in self.mru:
                self.mru.remove(str(path))
            self.mru.append(str(path))
            return hit

        # (re)indexar
        extractor = next((e for e in EXTRACTORS if e.supports(doc["kind"])), None)
        if extractor is None:
            raise ValueError(f"Sin extractor para {doc['kind']}")

        raw = extractor.extract_text(path)
        sections = extractor.presection(raw)

        cfg = self._chunk_cfg_for(doc["kind"]) 
        chunks = Chunker(cfg).chunk(sections, path, doc["kind"]) 
        embeddings = self.embedder.encode_texts([c["text"] for c in chunks])

        idx: IndexedDoc = {"etag": etag, "kind": doc["kind"], "chunks": chunks, "embeddings": embeddings}
        self.indices[str(path)] = idx
        if str(path) in self.mru:
            self.mru.remove(str(path))
        self.mru.append(str(path))
        self._ensure_capacity()
        _d(f"Indexado {path.name}: {len(chunks)} chunks")
        return idx

    def _chunk_cfg_for(self, kind: Kind) -> ChunkingConfig:
        if kind == "md":
            return ChunkingConfig(tokens=MD_CHUNK_TOKENS, overlap=MD_OVERLAP_TOKENS)
        if kind == "docx":
            return ChunkingConfig(tokens=DOCX_CHUNK_TOKENS, overlap=DOCX_OVERLAP_TOKENS)
        return ChunkingConfig(tokens=PDF_CHUNK_TOKENS, overlap=PDF_OVERLAP_TOKENS)


# ==========================
# QueryEngine
# ==========================


class QueryEngine:
    def __init__(self, store: IndexStore) -> None:
        self.store = store

    def _route_auto(self, query: str, defaults: List[str]) -> List[DocumentRef]:
        # Heurística simple basada en palabras clave
        q = query.lower()
        mapping: List[Tuple[List[str], str]] = [
            (["orden", "cier", "pago", "propina", "estado"], "guia_ordenes_md.md"),
            (["mesa", "área", "area", "asign"], "guia_mesas_md.md"),
            (["menú", "menu", "categoría", "impuesto", "producto"], "guia_menus_md.md"),
            (["beneficio", "visión", "implementación", "ejecutivo"], "resumen_ejecutivo_gastrosoft.docx"),
            (["práctica", "operación", "estándar", "buenas"], "buenas_practicas_gastrosoft.pdf"),
        ]
        picks: set[str] = set()
        for keys, fname in mapping:
            if any(k in q for k in keys):
                picks.add(fname)
        # si no hay match, usar todos por defecto
        chosen = list(picks) if picks else [Path(f).name for f in defaults]
        # construir DocumentRef con kind
        out: List[DocumentRef] = []
        for f in defaults:
            p = Path(f)
            if Path(f).name in chosen:
                out.append(DocumentRef(path=str(p), kind=_detect_kind(p)))  # type: ignore[arg-type]
        # fallback: si chosen venía por nombres y no match con defaults, incluir todos
        if not out:
            for f in defaults:
                p = Path(f)
                out.append(DocumentRef(path=str(p), kind=_detect_kind(p)))  # type: ignore[arg-type]
        return out

    def route_candidates(self, query: str, scope: str, files: Optional[List[str]]) -> List[DocumentRef]:
        if scope == "files" and files:
            refs: List[DocumentRef] = []
            for f in files:
                p = Path(f)
                refs.append(DocumentRef(path=str(p), kind=_detect_kind(p)))  # type: ignore[arg-type]
            return refs
        # auto: usar heurística con DEFAULT_FILES como universo
        return self._route_auto(query, DEFAULT_FILES)

    def _cosine_sim(self, a: np.ndarray, B: np.ndarray) -> np.ndarray:
        # a: [dim], B: [n, dim]
        a_norm = a / (np.linalg.norm(a) + 1e-8)
        B_norm = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-8)
        return B_norm @ a_norm

    def search(self, query: str, candidates: List[DocumentRef], top_k: int) -> Tuple[List[Result], bool]:
        t0 = time.time()
        qv = self.store.embedder.encode_query(query)
        per_doc_results: List[Result] = []
        indexed: List[str] = []
        skipped: List[str] = []

        for doc in candidates:
            try:
                idx = self.store.ensure_indexed(doc)
                sims = self._cosine_sim(qv, idx["embeddings"])  # shape [n]
                # top-k local por doc
                k = max(1, min(top_k, len(sims)))
                top_idx = np.argsort(-sims)[:k]
                for ti in top_idx:
                    ch = idx["chunks"][int(ti)]
                    score = float(sims[int(ti)])
                    src = f"{ch['meta']['path']}#{ch['meta']['locator']}"
                    per_doc_results.append(Result(source=src, score=score, snippet=ch["text"]))
                indexed.append(doc["path"])  # type: ignore[index]
            except Exception as e:  # extracción/soporte/IO
                skipped.append(f"{doc['path']}: {e}")  # type: ignore[index]

        # fusión y ranking global
        per_doc_results.sort(key=lambda r: r["score"], reverse=True)
        fused = per_doc_results[: top_k]

        max_score = fused[0]["score"] if fused else 0.0
        low_conf = bool(max_score < MIN_ACCEPTED)

        t1 = time.time()
        self.last_debug = {  # type: ignore[attr-defined]
            "indexed": indexed,
            "skipped": skipped,
            "timings_ms": {
                "total_ms": int((t1 - t0) * 1000),
            },
        }
        return fused, low_conf

    def compose_answer(self, ranked: List[Result]) -> str:
        if not ranked:
            return "No encontré suficiente contexto en los documentos locales para responder con confianza."
        # Combinar 1–2 pasajes si son del mismo source y cercanos
        top = ranked[0]
        answer = top["snippet"].strip()
        if len(ranked) > 1:
            top2 = ranked[1]
            if top2["source"].split("#")[0] == top["source"].split("#")[0]:
                # misma fuente: concatenar brevemente
                answer = (answer + "\n\n" + top2["snippet"]).strip()
        return answer


# ==========================
# ToolAdapter (API estable para ADK)
# ==========================


class ToolAdapter:
    def __init__(self) -> None:
        self.embedder = EmbedderService()
        self.store = IndexStore(self.embedder)
        self.engine = QueryEngine(self.store)

    def _ensure_defaults_exist(self) -> None:
        missing = [f for f in DEFAULT_FILES if not Path(f).exists()]
        if missing:
            raise FileNotFoundError(
                "No se encontraron rutas declaradas en UNSTRUCTURED_FILES: " + ", ".join(missing)
            )

    def run(self, args: Dict) -> Dict:
        """Punto de entrada principal.
        Args esperados:
          - query: str (obligatorio)
          - scope: "auto" | "files" (opcional)
          - files: [str] (opcional; requerido si scope="files")
          - top_k: int (opcional)
        """
        self._ensure_defaults_exist()

        query = (args.get("query") or "").strip()
        if not query:
            raise ValueError("'query' es obligatorio")
        scope = args.get("scope") or "auto"
        files = args.get("files") or None
        top_k = int(args.get("top_k") or TOP_K_DEFAULT)

        cands = self.engine.route_candidates(query, scope, files)
        ranked, low_conf = self.engine.search(query, cands, top_k)
        best_answer = self.engine.compose_answer(ranked)

        debug = getattr(self.engine, "last_debug", {"indexed": [], "skipped": [], "timings_ms": {}})
        return {
            "best_answer": best_answer,
            "low_confidence": low_conf,
            "results": ranked,
            "debug": debug,
        }


# ==========================
# Helpers CLI para pruebas locales (opcional)
# ==========================

def run_tool(args_json: str) -> str:
    """Función utilitaria para ejecutar desde CLI o tests.
    Ejemplo:
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
