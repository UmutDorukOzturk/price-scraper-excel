"""Compare two snapshots of the catalogue and list what changed."""
import pandas as pd

CHANGE_COLUMNS = [
    "change", "title", "category", "old_price", "new_price", "diff", "diff_pct",
    "old_stock", "new_stock", "url",
]


def compare(previous: pd.DataFrame, current: pd.DataFrame, key: str = "upc") -> pd.DataFrame:
    """Return one row per change: price up/down, stock in/out, new or removed products."""
    prev = previous.set_index(key)
    curr = current.set_index(key)
    rows = []

    for upc in curr.index.intersection(prev.index):
        old, new = prev.loc[upc], curr.loc[upc]
        base = {
            "title": new["title"], "category": new["category"], "url": new["url"],
            "old_price": old["price"], "new_price": new["price"],
            "old_stock": old["stock"], "new_stock": new["stock"],
        }
        if round(new["price"] - old["price"], 2) != 0:
            diff = round(new["price"] - old["price"], 2)
            rows.append({**base, "change": "Price up" if diff > 0 else "Price down",
                         "diff": diff, "diff_pct": diff / old["price"] if old["price"] else None})
        if old["stock"] > 0 and new["stock"] == 0:
            rows.append({**base, "change": "Out of stock"})
        elif old["stock"] == 0 and new["stock"] > 0:
            rows.append({**base, "change": "Back in stock"})

    for upc in curr.index.difference(prev.index):
        new = curr.loc[upc]
        rows.append({"change": "New product", "title": new["title"], "category": new["category"],
                     "new_price": new["price"], "new_stock": new["stock"], "url": new["url"]})

    for upc in prev.index.difference(curr.index):
        old = prev.loc[upc]
        rows.append({"change": "Removed", "title": old["title"], "category": old["category"],
                     "old_price": old["price"], "old_stock": old["stock"], "url": old["url"]})

    order = {"Price down": 0, "Price up": 1, "Out of stock": 2, "Back in stock": 3, "New product": 4, "Removed": 5}
    changes = pd.DataFrame(rows, columns=CHANGE_COLUMNS)
    if changes.empty:
        return changes
    changes["_order"] = changes["change"].map(order)
    changes["_size"] = changes["diff_pct"].abs()
    return (changes.sort_values(["_order", "_size", "title"], ascending=[True, False, True], na_position="last")
                   .drop(columns=["_order", "_size"]).reset_index(drop=True))
