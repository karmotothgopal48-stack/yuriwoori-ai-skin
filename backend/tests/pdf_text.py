"""Text and image count of a ReportLab PDF (streams are ASCII85 + Flate), for the report tests."""
import base64
import re
import sys
import zlib


def pdf_text(data: bytes) -> str:
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        raw = m.group(1).strip()
        for decode in (lambda b: zlib.decompress(base64.a85decode(b, adobe=True)), zlib.decompress):
            try:
                out.append(decode(raw))
                break
            except Exception:
                continue
    content = b"\n".join(out)
    parts = re.findall(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj", content)
    return " ".join(p.decode("latin-1").replace("\\(", "(").replace("\\)", ")") for p in parts)


if __name__ == "__main__":
    data = open(sys.argv[1], "rb").read()
    text = pdf_text(data)
    print("pages:", len(re.findall(rb"/Type /Page\b", data)), "| embedded images:", len(re.findall(rb"/Subtype /Image", data)))
    for needle in sys.argv[2:]:
        print(("  OK      " if needle in text else "  MISSING ") + needle)
