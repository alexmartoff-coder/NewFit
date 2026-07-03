def escape_md(text: str) -> str:
    """Helper to escape underscores for MarkdownV1"""
    if text is None:
        return ""
    # Standard escaping for MarkdownV1 in aiogram
    # _ * [ ` are the main ones to worry about for simple text
    return str(text).replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
