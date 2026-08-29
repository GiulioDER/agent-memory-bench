def slugify(value: str) -> str:
    return "-".join(value.lower().split())


def titlecase(value: str) -> str:
    return " ".join(word.capitalize() for word in value.split())
