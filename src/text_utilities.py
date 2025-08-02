import re, gzip, base64, json, typing as t

def remove_curly_braces_and_content(text: str) -> str:
    """
    Removes all occurrences of content enclosed in curly braces,
    including the braces themselves, from a string.
    """
    # The regex pattern \{.*?\} means:
    # \{    - Match a literal opening curly brace. We need to escape it with \
    # .*?   - Match any character (.), zero or more times (*), non-greedily (?).
    #         The non-greedy part is crucial so it doesn't match across multiple sets of braces.
    # \}    - Match a literal closing curly brace. We need to escape it with \
    return re.sub(r"\{.*?\}", "", text)

def compress(obj: t.Any) -> str:
    raw_bytes = json.dumps(obj).encode()          # → bytes
    gz_bytes  = gzip.compress(raw_bytes, 9)       # max compression
    b64_bytes = base64.b64encode(gz_bytes)
    return "gz64:" + b64_bytes.decode()           # add a magic prefix

def decompress(s: str) -> t.Any:
    if not s.startswith("gz64:"):
        return json.loads(s)                      # legacy / uncompressed
    b64_bytes = base64.b64decode(s[5:])
    raw_bytes = gzip.decompress(b64_bytes)
    return json.loads(raw_bytes)
