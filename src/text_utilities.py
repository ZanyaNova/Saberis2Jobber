import re

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