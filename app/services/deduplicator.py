import hashlib
import re


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def make_dedup_hash(title: str, company: str, location: str) -> str:
    """
    Hash on normalized (title + company + location).
    Small variations in spacing/case won't create duplicates.
    """
    key = f"{normalize(title)}|{normalize(company)}|{normalize(location)}"
    return hashlib.sha256(key.encode()).hexdigest()
