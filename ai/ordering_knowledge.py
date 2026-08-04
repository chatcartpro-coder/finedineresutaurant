"""
Per-category clarifying-question guidance for the ordering assistant - the
practical "restaurant knowledge base" for this project. Rather than a
separate RAG/vector-search system (overkill for ~34 menu categories and a
fixed rule set), this is a small, explicit, human-editable mapping injected
into the system prompt as grounded guidance: it tells the AI *what to ask*
before finalizing a line item in a given category, never *what exists* -
menu items/prices still only ever come from the real catalog data, so this
can't cause the AI to invent anything.

Edit this file directly to add/adjust clarifying questions as the menu or
restaurant's preferences change - no code changes needed elsewhere.
"""

CATEGORY_CLARIFICATIONS = {
    "Shawarma": "Ask if they'd like it spicy or normal.",
    "Charcoal Special": (
        "This category has several charcoal varieties (chicken, green chilli, pepper, peri peri, "
        "malai, honey chilli, etc.) - list 2-3 relevant ones from the menu context and ask which "
        "they'd like, and whether they want Half or Full."
    ),
    "Tandoor": "Ask if they'd like it spicy or mild if the dish name doesn't already specify.",
    "Hot Beverages": (
        "Ask how sweet they'd like it (e.g. no sugar, less sweet, normal, extra sweet) and, for "
        "tea/karak specifically, how strong they want it brewed."
    ),
    "North Indian Non-Veg": "Ask if they'd like it spicy or mild if the dish name doesn't already specify.",
    "Chinese Curry": "Ask if they'd like it spicy or mild if the dish name doesn't already specify.",
}


def get_clarification_hints(categories: set) -> str:
    """Returns the clarification guidance relevant to the given set of
    category names (typically the categories present in the current turn's
    catalog search results) - only shows what's relevant to this turn, same
    discipline as the catalog-context formatting in ai/agent.py."""
    relevant = {cat: hint for cat, hint in CATEGORY_CLARIFICATIONS.items() if cat in categories}
    if not relevant:
        return "(No category-specific clarifications apply to the items shown above.)"
    return "\n".join(f"- {cat}: {hint}" for cat, hint in relevant.items())
