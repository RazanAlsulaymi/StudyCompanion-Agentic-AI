import io
from typing import List


def extract_text_from_upload(file_storage) -> str:
    filename = (getattr(file_storage, "filename", "") or "").lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

    data = file_storage.read()

    if not data:
        raise ValueError("Uploaded file is empty.")

    if len(data) > 20 * 1024 * 1024:
        raise ValueError("File too large (max 20 MB).")

    if ext in {"txt", "md"}:
        return data.decode("utf-8", errors="ignore")

    if ext == "pdf":
        try:
            from pypdf import PdfReader
        except Exception as e:
            raise RuntimeError(
                "PDF support requires 'pypdf' on server."
            ) from e

        reader = PdfReader(io.BytesIO(data))

        pages_text: List[str] = []

        for page in reader.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                continue

        text = "\n".join(pages_text).strip()

        if not text:
            raise ValueError("Could not extract text from the PDF.")

        return text

    raise ValueError(
        "Unsupported file type. Use .txt, .md, or .pdf."
    )