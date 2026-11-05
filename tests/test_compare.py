import pandas as pd

from price_scraper.compare import compare


def frame(rows):
    return pd.DataFrame(rows, columns=["upc", "title", "category", "price", "stock", "url"])


def test_detects_price_stock_new_and_removed():
    previous = frame([
        ("a", "Cheaper now", "Poetry", 20.00, 5, "u/a"),
        ("b", "Dearer now", "Poetry", 10.00, 5, "u/b"),
        ("c", "Sold out", "Music", 15.00, 3, "u/c"),
        ("d", "Gone", "Music", 12.00, 1, "u/d"),
        ("e", "Unchanged", "Music", 9.99, 2, "u/e"),
    ])
    current = frame([
        ("a", "Cheaper now", "Poetry", 15.00, 5, "u/a"),
        ("b", "Dearer now", "Poetry", 12.50, 5, "u/b"),
        ("c", "Sold out", "Music", 15.00, 0, "u/c"),
        ("e", "Unchanged", "Music", 9.99, 2, "u/e"),
        ("f", "Brand new", "Art", 30.00, 7, "u/f"),
    ])
    changes = compare(previous, current)

    assert list(changes["change"]) == ["Price down", "Price up", "Out of stock", "New product", "Removed"]
    down = changes.iloc[0]
    assert down["title"] == "Cheaper now"
    assert down["diff"] == -5.00
    assert round(down["diff_pct"], 2) == -0.25


def test_no_changes_gives_empty_frame():
    snap = frame([("a", "Same", "Poetry", 10.0, 1, "u/a")])
    assert compare(snap, snap.copy()).empty
