"""
Per-category and per-item clarifying-question guidance for the ordering
assistant - the practical "restaurant knowledge base" for this project.
Rather than a separate RAG/vector-search system (overkill for ~34 menu
categories and a fixed rule set), this is a small, explicit, human-editable
mapping injected into the system prompt as grounded guidance: it tells the
AI *what to ask* before finalizing a line item, never *what exists* - menu
items/prices still only ever come from the real catalog data, so this can't
cause the AI to invent anything.

Item-level entries (ITEM_CLARIFICATIONS) take priority over category-level
ones (CATEGORY_CLARIFICATIONS) - needed because a category can mix items
that don't share the same real-world preparation. E.g. "Hot Beverages"
includes both milk teas that take sugar/milk-strength preferences (Karak,
Fresh Milk Tea, Coffee) and plain infusions that don't (Green Tea, Sulaimani,
Black Mint/Ginger Tea, which are typically unsweetened, no milk) - applying
one blanket "ask sweetness and brew strength" rule to the whole category
produced a nonsensical question for green tea.

Edit this file directly to add/adjust clarifying questions as the menu or
restaurant's preferences change - no code changes needed elsewhere.
"""

ITEM_CLARIFICATIONS = {
    "Karak": "Ask how sweet they'd like it (no sugar, less sweet, normal, extra sweet) and how strong they want it brewed.",
    "Fresh Milk Tea": "Ask how sweet they'd like it (no sugar, less sweet, normal, extra sweet).",
    "Coffee": "Ask how sweet they'd like it (no sugar, less sweet, normal, extra sweet).",
    "Green Tea": "Ask if they'd like sugar or prefer it plain - don't ask about milk or brew strength, this is a plain infusion.",
    "Sulaimani": "Ask if they'd like sugar or prefer it plain - don't ask about milk or brew strength, this is a plain infusion.",
    "Black Mint Tea": "Ask if they'd like sugar or prefer it plain - don't ask about milk or brew strength, this is a plain infusion.",
    "Black Ginger Tea": "Ask if they'd like sugar or prefer it plain - don't ask about milk or brew strength, this is a plain infusion.",
}

CATEGORY_CLARIFICATIONS = {
    "Shawarma": "Ask if they'd like it spicy or normal.",
    "Charcoal Special": (
        "This category has several charcoal varieties (chicken, green chilli, pepper, peri peri, "
        "malai, honey chilli, etc.) - list 2-3 relevant ones from the menu context and ask which "
        "they'd like, and whether they want Half or Full."
    ),
    "Tandoor": "Ask if they'd like it spicy or mild if the dish name doesn't already specify.",
    "North Indian Non-Veg": "Ask if they'd like it spicy or mild if the dish name doesn't already specify.",
    "Chinese Curry": "Ask if they'd like it spicy or mild if the dish name doesn't already specify.",
}


def get_clarification_hints(items: list) -> str:
    """items: the catalog items shown in this turn's menu context (each a
    dict with at least "name" and "category"). Item-specific guidance wins
    over category-level guidance for the same item, so a mixed category
    (like Hot Beverages) doesn't get one-size-fits-all questions applied to
    items that don't fit them."""
    lines = []
    seen_categories = set()
    for it in items:
        name, category = it.get("name"), it.get("category")
        if name in ITEM_CLARIFICATIONS:
            lines.append(f"- {name}: {ITEM_CLARIFICATIONS[name]}")
        elif category in CATEGORY_CLARIFICATIONS and category not in seen_categories:
            seen_categories.add(category)
            lines.append(f"- {category}: {CATEGORY_CLARIFICATIONS[category]}")
    if not lines:
        return "(No clarifications apply to the items shown above.)"
    return "\n".join(lines)
