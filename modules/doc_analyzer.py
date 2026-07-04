"""DocAnalyzer V3 - REAL document metadata extraction - Ghost1o1
Sources (NO API KEYS NEEDED):
- python-docx (DOCX metadata)
- openpyxl (XLSX metadata)
- PyPDF2 / pypdf (PDF metadata)
- exiftool (if installed)
- MIME type detection (magic)

API keys optional:
- VirusTotal (paid, ~$200/mo)
- MetaDefender (paid)
"""
import time, hashlib, os, re, json
from urllib.parse import quote_plus
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED
from typing import Dict, List, Any, Optional


class DocAnalyzer(OSINTModule):
    module_name = "DocAnalyzer"
    module_icon = "📄"
    module_description = "Document metadata extraction (PDF, DOCX, XLSX, etc.) + VirusTotal check"
    input_type = "document"
    output_types = ["name", "email", "company", "url", "exif_field", "datetime"]
    api_requirements = []
    needs_internet = False  # works offline mostly

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = entity.get("value", "").strip()
        meta = entity.get("metadata", {})

        # Get document bytes
        doc_bytes = None
        file_path = meta.get("file_path")
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                doc_bytes = f.read()
        elif meta.get("base64"):
            import base64
            doc_bytes = base64.b64decode(meta["base64"])
        elif val.startswith("http"):
            try:
                resp = self.session.get(val, timeout=15)
                if resp.status_code == 200:
                    doc_bytes = resp.content
            except Exception:
                pass

        if not doc_bytes:
            r.errors.append("Aucun fichier fourni (file_path, base64 ou URL)")
            r.execution_time_ms = (time.time() - t0) * 1000
            r.status = "failed"; return r

        root_id = f"doc_{hashlib.md5(doc_bytes[:1024]).hexdigest()[:12]}"
        r.entities_found.append(self._new_entity(
            "document_hash", hashlib.sha256(doc_bytes).hexdigest(),
            "sha256",
            confidence=1.0, status=STATUS_VERIFIED,
            metadata={"size_bytes": len(doc_bytes),
                      "sha256": hashlib.sha256(doc_bytes).hexdigest(),
                      "md5": hashlib.md5(doc_bytes).hexdigest(),
                      "filename": os.path.basename(file_path) if file_path else val}
        ))
        r.entities_found[-1]["id"] = root_id

        # ─── 1. Detect file type ───
        mime = self._detect_mime(doc_bytes)
        r.raw_data = {"mime": mime, "size": len(doc_bytes)}

        # ─── 2. PDF metadata ───
        if "pdf" in mime.lower() or doc_bytes[:4] == b"%PDF":
            pdf_meta = self._pdf_metadata(doc_bytes)
            for k, v in pdf_meta.items():
                e = self._new_entity(
                    "pdf_metadata", f"{k}: {str(v)[:100]}", "pdf_metadata",
                    confidence=1.0, status=STATUS_VERIFIED,
                    metadata={"field": k, "value": str(v)[:300]}
                )
                r.entities_found.append(e)
                # Extract author as name
                if k.lower() in ["author", "creator"] and v:
                    ne = self._new_entity(
                        "name", str(v)[:100], "pdf_metadata",
                        confidence=0.95, status=STATUS_VERIFIED,
                        metadata={"via": "pdf_author"}
                    )
                    r.entities_found.append(ne)
            if pdf_meta:
                r.sources_hit.append("PyPDF2 metadata extraction")

        # ─── 3. DOCX metadata ───
        if "wordprocessingml" in mime or doc_bytes[:4] == b"PK\x03\x04":
            try:
                docx_meta = self._docx_metadata(doc_bytes)
                for k, v in docx_meta.items():
                    e = self._new_entity(
                        "docx_metadata", f"{k}: {str(v)[:100]}", "docx_metadata",
                        confidence=1.0, status=STATUS_VERIFIED,
                        metadata={"field": k, "value": str(v)[:300]}
                    )
                    r.entities_found.append(e)
                    if k.lower() in ["author", "last_modified_by"] and v:
                        ne = self._new_entity(
                            "name", str(v)[:100], "docx_metadata",
                            confidence=0.95, status=STATUS_VERIFIED,
                            metadata={"via": "docx_author"}
                        )
                        r.entities_found.append(ne)
                if docx_meta:
                    r.sources_hit.append("python-docx metadata")
            except Exception:
                pass

        # ─── 4. XLSX metadata ───
        if "spreadsheetml" in mime:
            try:
                xlsx_meta = self._xlsx_metadata(doc_bytes)
                for k, v in xlsx_meta.items():
                    e = self._new_entity(
                        "xlsx_metadata", f"{k}: {str(v)[:100]}", "xlsx_metadata",
                        confidence=1.0, status=STATUS_VERIFIED,
                        metadata={"field": k, "value": str(v)[:300]}
                    )
                    r.entities_found.append(e)
                if xlsx_meta:
                    r.sources_hit.append("openpyxl metadata")
            except Exception:
                pass

        # ─── 5. Exiftool if available (REAL, system tool) ───
        et = self._exiftool_meta(doc_bytes, file_path)
        for e in et:
            r.entities_found.append(e)
        if et:
            r.sources_hit.append("exiftool (system tool)")

        # ─── 6. Extract emails/URLs from text ───
        text = doc_bytes[:100000].decode('utf-8', errors='ignore')
        for em in set(re.findall(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b', text))[:10]:
            e = self._new_entity(
                "email", em, "doc_text_scan",
                confidence=0.85, status=STATUS_VERIFIED,
                metadata={"via": "regex_in_doc_content"}
            )
            r.entities_found.append(e)
        for url in set(re.findall(r'https?://[^\s<>"]{8,80}', text))[:10]:
            e = self._new_entity(
                "url", url, "doc_text_scan",
                confidence=0.85, status=STATUS_VERIFIED,
                metadata={"via": "regex_in_doc_content"}
            )
            r.entities_found.append(e)

        # ─── 7. Optional VirusTotal ───
        if self.config and getattr(self.config, "VIRUSTOTAL_API_KEY", None):
            vt = self._virustotal(doc_bytes)
            for e in vt["entities"]:
                r.entities_found.append(e)
            if vt.get("hit"):
                r.sources_hit.append("virustotal.com (paid)")

        r.execution_time_ms = (time.time() - t0) * 1000
        return r

    def _detect_mime(self, doc_bytes: bytes) -> str:
        try:
            import magic
            return magic.from_buffer(doc_bytes, mime=True)
        except Exception:
            # Fallback by signature
            if doc_bytes[:4] == b"%PDF":
                return "application/pdf"
            elif doc_bytes[:2] == b"PK":
                return "application/zip"
            elif doc_bytes[:4] == b"\x89PNG":
                return "image/png"
            return "application/octet-stream"

    def _pdf_metadata(self, doc_bytes: bytes) -> Dict:
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(doc_bytes))
            out = {}
            if reader.metadata:
                for k, v in reader.metadata.items():
                    key = str(k).strip("/")
                    val = str(v)[:300]
                    if val:
                        out[key] = val
            return out
        except Exception as ex:
            return {"error": str(ex)[:100]}

    def _docx_metadata(self, doc_bytes: bytes) -> Dict:
        try:
            from docx import Document
            import io
            doc = Document(io.BytesIO(doc_bytes))
            cp = doc.core_properties
            return {
                "author": str(cp.author or ""),
                "last_modified_by": str(cp.last_modified_by or ""),
                "title": str(cp.title or ""),
                "subject": str(cp.subject or ""),
                "comments": str(cp.comments or ""),
                "category": str(cp.category or ""),
                "created": str(cp.created) if cp.created else "",
                "modified": str(cp.modified) if cp.modified else "",
            }
        except Exception as ex:
            return {"error": str(ex)[:100]}

    def _xlsx_metadata(self, doc_bytes: bytes) -> Dict:
        try:
            from openpyxl import load_workbook
            wb = load_workbook(filename=None, file_contents=doc_bytes)
            return {
                "creator": str(wb.properties.creator or ""),
                "last_modified_by": str(wb.properties.lastModifiedBy or ""),
                "title": str(wb.properties.title or ""),
                "subject": str(wb.properties.subject or ""),
                "company": str(wb.properties.company or "") if hasattr(wb.properties, 'company') else "",
            }
        except Exception as ex:
            return {"error": str(ex)[:100]}

    def _exiftool_meta(self, doc_bytes: bytes, file_path: str) -> list:
        entities = []
        try:
            import subprocess
            if file_path and os.path.exists(file_path):
                result = subprocess.run(["exiftool", "-j", file_path],
                                          capture_output=True, timeout=15)
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    if data:
                        for k, v in list(data[0].items())[:30]:
                            if v and k not in ["ExifToolVersion", "FileName",
                                                "Directory", "FileSize", "FileModifyDate"]:
                                e = self._new_entity(
                                    "exiftool_field", f"{k}: {str(v)[:80]}",
                                    "exiftool",
                                    confidence=1.0, status=STATUS_VERIFIED,
                                    metadata={"field": k, "value": str(v)[:300]}
                                )
                                entities.append(e)
        except Exception:
            pass
        return entities

    def _virustotal(self, doc_bytes: bytes) -> Dict:
        out = {"entities": [], "hit": False}
        key = getattr(self.config, "VIRUSTOTAL_API_KEY", None)
        if not key:
            return out
        try:
            # Upload file (small files only)
            files = {"file": ("doc.bin", doc_bytes)}
            r = self.session.post(
                "https://www.virustotal.com/api/v3/files",
                files=files,
                headers={"x-apikey": key},
                timeout=30
            )
            if r.status_code == 200:
                d = r.json()
                analysis_id = d.get("data", {}).get("id", "")
                if analysis_id:
                    e = self._new_entity(
                        "virustotal_scan", analysis_id, "virustotal",
                        confidence=1.0, status=STATUS_VERIFIED,
                        metadata={"analysis_id": analysis_id},
                        source_url=f"https://www.virustotal.com/gui/file/{d['data']['id']}"
                    )
                    out["entities"].append(e)
                    out["hit"] = True
        except Exception:
            pass
        return out