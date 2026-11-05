"""Extracción de artículos y secciones; no ejecuta instrucciones de las fuentes."""
from bs4 import BeautifulSoup, NavigableString, Tag

def inline(node):
    return node.get_text("", strip=False) if isinstance(node, Tag) else str(node)

def render(node):
    if isinstance(node, NavigableString):
        return str(node)
    if node.name in ("script", "style", "nav", "button", "svg", "img", "form") or node.get("id", "").startswith("ms--"):
        return ""
    if node.name == "pre":
        return "\n```\n" + node.get_text().rstrip() + "\n```\n"
    if node.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return "\n" + "#" * int(node.name[1]) + " " + node.get_text(" ", strip=True) + "\n"
    if node.name in ("p", "dt", "dd"):
        return inline(node).strip() + "\n\n"
    if node.name == "li" and not node.find(["p", "pre", "ul", "ol"]):
        return "- " + inline(node).strip() + "\n"
    if node.name == "table":
        return "\n" + "\n".join(" | ".join(inline(cell).strip() for cell in row.find_all(["th", "td"], recursive=False)) for row in node.find_all("tr")) + "\n\n"
    return "".join(render(child) for child in node.children)

def select_section(article, identifier):
    if identifier is None:
        return article
    heading = article.find(id=identifier)
    if heading is None or heading.name not in ("h2", "h3", "h4"):
        raise ValueError("Sección no encontrada: " + identifier)
    level = int(heading.name[1])
    result = BeautifulSoup("<div></div>", "html.parser").div
    for current in [heading, *list(heading.next_siblings)]:
        if current is not heading and isinstance(current, Tag) and current.name in ("h1", "h2", "h3", "h4", "h5", "h6") and int(current.name[1]) <= level:
            break
        result.append(BeautifulSoup(str(current), "html.parser"))
    return result
