"""Excel report: Summary dashboard, full product list, categories, price changes and notes."""
import math
from datetime import datetime
from typing import Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

NAVY, BLUE, LIGHT, GREY = "1F3864", "2E75B6", "EEF3FA", "6B7280"
GREEN, RED = "16794A", "C0392B"
MONEY = "£#,##0.00"
DIFF_MONEY = "+£#,##0.00;-£#,##0.00;£0.00"
DIFF_PCT = "+0.0%;-0.0%;0.0%"
TABLE_STYLE = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
CHANGE_LABELS = {
    "Price down": ("▼ Price down", GREEN), "Price up": ("▲ Price up", RED),
    "Out of stock": ("✕ Out of stock", RED), "Back in stock": ("✓ Back in stock", GREEN),
    "New product": ("+ New product", BLUE), "Removed": ("− Removed", GREY),
}


def write_report(df: pd.DataFrame, path: str, scraped_at: datetime, source: str,
                 changes: Optional[pd.DataFrame] = None, previous_label: Optional[str] = None) -> None:
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    products = wb.create_sheet("Products")
    categories = wb.create_sheet("Categories")
    changes_ws = wb.create_sheet("Price changes")
    notes = wb.create_sheet("Notes")

    _products_sheet(products, df)
    cat_rows, band_ref, rating_ref = _categories_sheet(categories, df)
    _changes_sheet(changes_ws, changes, previous_label)
    _summary_sheet(summary, df, scraped_at, source, changes, previous_label, categories, cat_rows, band_ref, rating_ref)
    _notes_sheet(notes, df, scraped_at, source, previous_label)
    wb.save(path)


# ---------------------------------------------------------------- helpers

def _header_row(ws, row: int, headers: list[str], widths: list[float], start_col: int = 1) -> None:
    for i, (text, width) in enumerate(zip(headers, widths)):
        col = start_col + i
        ws.cell(row=row, column=col, value=text)
        ws.column_dimensions[get_column_letter(col)].width = width


def _add_table(ws, name: str, first_row: int, last_row: int, first_col: int, last_col: int) -> None:
    ref = f"{get_column_letter(first_col)}{first_row}:{get_column_letter(last_col)}{max(last_row, first_row + 1)}"
    table = Table(displayName=name, ref=ref)
    table.tableStyleInfo = TABLE_STYLE
    ws.add_table(table)


def _bar_chart(title: str, cats: Reference, vals: Reference, horizontal: bool, color: str,
               label_fmt: Optional[str] = None) -> BarChart:
    chart = BarChart()
    chart.type = "bar" if horizontal else "col"
    chart.title = title
    chart.title.overlay = False
    chart.add_data(vals, titles_from_data=False)
    chart.set_categories(cats)
    chart.legend = None
    chart.varyColors = False
    chart.gapWidth = 55
    series = chart.series[0]
    series.graphicalProperties.solidFill = color
    series.graphicalProperties.line.solidFill = color
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showVal = True
    for flag in ("showSerName", "showCatName", "showLegendKey", "showPercent"):
        setattr(chart.dataLabels, flag, False)
    if label_fmt:
        chart.dataLabels.numFmt = label_fmt
    chart.x_axis.delete = False
    chart.y_axis.delete = True
    chart.y_axis.majorGridlines = None
    if horizontal:
        chart.x_axis.scaling.orientation = "maxMin"  # largest bar on top
    chart.width, chart.height = 12.6, 7.6
    return chart


# ---------------------------------------------------------------- sheets

def _products_sheet(ws, df: pd.DataFrame) -> None:
    headers = ["Title", "Category", "Price", "Rating", "Stars", "Units in stock", "Reviews", "UPC",
               "Product page", "Description"]
    widths = [52, 20, 11, 9, 11, 15, 10, 19, 14, 90]
    _header_row(ws, 1, headers, widths)
    ordered = df.sort_values("title", key=lambda s: s.str.lower())
    for r, row in enumerate(ordered.itertuples(index=False), start=2):
        ws.cell(r, 1, row.title)
        ws.cell(r, 2, row.category)
        ws.cell(r, 3, row.price).number_format = MONEY
        ws.cell(r, 4, row.rating).alignment = Alignment(horizontal="center")
        stars = ws.cell(r, 5, "★" * row.rating + "☆" * (5 - row.rating))
        stars.font = Font(color="D4A017")
        ws.cell(r, 6, row.stock)
        ws.cell(r, 7, row.reviews)
        ws.cell(r, 8, row.upc)
        link = ws.cell(r, 9, "Open ↗")
        link.hyperlink = row.url
        link.font = Font(color=BLUE, underline="single")
        ws.cell(r, 10, row.description)
    last = len(df) + 1
    _add_table(ws, "Products", 1, last, 1, len(headers))
    ws.conditional_formatting.add(f"F2:F{last}", DataBarRule(start_type="num", start_value=0,
                                                              end_type="max", color="9BC2E6"))
    ws.freeze_panes = "B2"


def _categories_sheet(ws, df: pd.DataFrame):
    cats = (df.groupby("category")
              .agg(products=("upc", "count"), avg_price=("price", "mean"), min_price=("price", "min"),
                   max_price=("price", "max"), avg_rating=("rating", "mean"), units=("stock", "sum"))
              .sort_values(["products", "avg_price"], ascending=[False, False])
              .reset_index())
    cats["share"] = cats["products"] / cats["products"].sum()

    headers = ["Category", "Products", "Avg price", "Min price", "Max price", "Avg rating",
               "Units in stock", "Share of catalogue"]
    _header_row(ws, 1, headers, [24, 11, 12, 12, 12, 12, 15, 19])
    formats = [None, "#,##0", MONEY, MONEY, MONEY, "0.0", "#,##0", "0.0%"]
    for r, row in enumerate(cats.itertuples(index=False), start=2):
        values = [row.category, row.products, row.avg_price, row.min_price, row.max_price,
                  row.avg_rating, row.units, row.share]
        for c, (value, fmt) in enumerate(zip(values, formats), start=1):
            cell = ws.cell(r, c, value)
            if fmt:
                cell.number_format = fmt
    last = len(cats) + 1
    _add_table(ws, "Categories", 1, last, 1, len(headers))
    ws.freeze_panes = "A2"

    # Small tables behind the Summary charts.
    lo = int(math.floor(df["price"].min() / 10) * 10)
    hi = int(math.ceil(df["price"].max() / 10) * 10)
    edges = list(range(lo, hi + 10, 10))
    bands = pd.cut(df["price"], bins=edges, right=False).value_counts().sort_index()
    ws["K1"], ws["L1"] = "Price band", "Products"
    for i, (interval, count) in enumerate(bands.items(), start=2):
        ws.cell(i, 11, f"£{int(interval.left)}–{int(interval.right)}")
        ws.cell(i, 12, int(count))
    band_last = len(bands) + 1
    _add_table(ws, "PriceBands", 1, band_last, 11, 12)

    ws["N1"], ws["O1"] = "Rating", "Products"
    counts = df["rating"].value_counts()
    for i, stars in enumerate(range(1, 6), start=2):
        ws.cell(i, 14, f"{stars} star" + ("s" if stars > 1 else ""))
        ws.cell(i, 15, int(counts.get(stars, 0)))
    _add_table(ws, "Ratings", 1, 6, 14, 15)
    for col, width in (("J", 3), ("K", 13), ("L", 11), ("M", 3), ("N", 11), ("O", 11)):
        ws.column_dimensions[col].width = width

    return len(cats), (2, band_last), (2, 6)


def _changes_sheet(ws, changes: Optional[pd.DataFrame], previous_label: Optional[str]) -> None:
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Price & stock changes"
    ws["A1"].font = Font(size=16, bold=True, color=NAVY)
    if changes is None:
        ws["A2"] = "First run: there is no previous snapshot to compare with yet. Run the scraper again later to see changes."
        ws["A2"].font = Font(color=GREY, italic=True)
        ws.column_dimensions["A"].width = 18
        return
    ws["A2"] = f"Compared with the snapshot from {previous_label}: {len(changes)} change(s)."
    ws["A2"].font = Font(color=GREY)

    headers = ["Change", "Title", "Category", "Old price", "New price", "Difference", "Change %",
               "Old stock", "New stock", "Product page"]
    _header_row(ws, 4, headers, [18, 50, 18, 12, 12, 13, 11, 11, 11, 14])
    for r, row in enumerate(changes.itertuples(index=False), start=5):
        label, color = CHANGE_LABELS.get(row.change, (row.change, NAVY))
        ws.cell(r, 1, label).font = Font(color=color, bold=True)
        ws.cell(r, 2, row.title)
        ws.cell(r, 3, row.category)
        for c, value, fmt in ((4, row.old_price, MONEY), (5, row.new_price, MONEY),
                              (6, row.diff, DIFF_MONEY), (7, row.diff_pct, DIFF_PCT)):
            if pd.notna(value):
                cell = ws.cell(r, c, float(value))
                cell.number_format = fmt
                if c >= 6:
                    cell.font = Font(color=color, bold=True)
        for c, value in ((8, row.old_stock), (9, row.new_stock)):
            if pd.notna(value):
                ws.cell(r, c, int(value))
        link = ws.cell(r, 10, "Open ↗")
        link.hyperlink = row.url
        link.font = Font(color=BLUE, underline="single")
    if not changes.empty:
        _add_table(ws, "PriceChanges", 4, len(changes) + 4, 1, len(headers))
    ws.freeze_panes = "A5"


def _kpi_card(ws, col: int, label: str, value, note: str, fmt: Optional[str] = None) -> None:
    fill = PatternFill("solid", fgColor=LIGHT)
    accent = Side(style="thick", color=BLUE)
    for row in (5, 6, 7):
        ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col + 1)
        for c in (col, col + 1):
            ws.cell(row, c).fill = fill
        ws.cell(row, col).border = Border(left=accent)
    top = ws.cell(5, col, label.upper())
    top.font = Font(size=9, bold=True, color=GREY)
    big = ws.cell(6, col, value)
    big.font = Font(size=20, bold=True, color=NAVY)
    if fmt:
        big.number_format = fmt
    small = ws.cell(7, col, note)
    small.font = Font(size=9, color=GREY)
    for row in (5, 6, 7):
        ws.cell(row, col).alignment = Alignment(horizontal="left", vertical="center", indent=1)


def _summary_sheet(ws, df, scraped_at, source, changes, previous_label, cat_ws, cat_rows, band_rows, rating_rows):
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 2
    for col in range(2, 14):
        ws.column_dimensions[get_column_letter(col)].width = 11.5
    ws.row_dimensions[6].height = 30

    ws["B2"] = "Book Catalogue · Price Report"
    ws["B2"].font = Font(size=20, bold=True, color=NAVY)
    ws["B3"] = (f"Source: {source}   ·   Scraped {scraped_at:%d %b %Y, %H:%M}   ·   "
                f"{len(df):,} products in {df['category'].nunique()} categories")
    ws["B3"].font = Font(size=10, color=GREY)

    n_changes = "—" if changes is None else len(changes)
    change_note = "first run" if changes is None else f"since {previous_label.split(',')[0]}"
    _kpi_card(ws, 2, "Products", len(df), "every catalogue page", "#,##0")
    _kpi_card(ws, 4, "Categories", df["category"].nunique(), "genres")
    _kpi_card(ws, 6, "Average price", df["price"].mean(), f"median £{df['price'].median():,.2f}", MONEY)
    _kpi_card(ws, 8, "Price range", f"£{df['price'].min():,.0f}–{df['price'].max():,.0f}", "cheapest to most expensive")
    _kpi_card(ws, 10, "Units in stock", int(df["stock"].sum()), "across all products", "#,##0")
    _kpi_card(ws, 12, "Changes", n_changes, change_note)

    top = min(10, cat_rows)
    chart = _bar_chart("Top 10 categories by number of products",
                       Reference(cat_ws, min_col=1, min_row=2, max_row=1 + top),
                       Reference(cat_ws, min_col=2, min_row=2, max_row=1 + top), True, BLUE)
    ws.add_chart(chart, "B9")
    chart = _bar_chart("Products per price band",
                       Reference(cat_ws, min_col=11, min_row=band_rows[0], max_row=band_rows[1]),
                       Reference(cat_ws, min_col=12, min_row=band_rows[0], max_row=band_rows[1]), False, NAVY)
    ws.add_chart(chart, "H9")
    chart = _bar_chart("Products per star rating",
                       Reference(cat_ws, min_col=14, min_row=rating_rows[0], max_row=rating_rows[1]),
                       Reference(cat_ws, min_col=15, min_row=rating_rows[0], max_row=rating_rows[1]), False, "D4A017")
    ws.add_chart(chart, "B25")

    # "What changed" box next to the rating chart.
    ws["H25"] = "What changed since the last run"
    ws["H25"].font = Font(size=12, bold=True, color=NAVY)
    if changes is None:
        ws["H27"] = "This is the first run. Every future run is compared with"
        ws["H28"] = "the previous one, and price or stock changes appear here"
        ws["H29"] = "and on the 'Price changes' sheet."
        for r in (27, 28, 29):
            ws[f"H{r}"].font = Font(color=GREY)
        return
    ws["H26"] = f"Compared with the snapshot of {previous_label}"
    ws["H26"].font = Font(size=9, color=GREY)
    counts = changes["change"].value_counts()
    line = Side(style="thin", color="D9E1F2")
    for i, key in enumerate(CHANGE_LABELS, start=28):
        label, color = CHANGE_LABELS[key]
        ws.merge_cells(start_row=i, start_column=8, end_row=i, end_column=11)
        ws.cell(i, 8, label).font = Font(bold=True, color=color)
        value = ws.cell(i, 12, int(counts.get(key, 0)))
        value.font = Font(bold=True, color=NAVY)
        value.alignment = Alignment(horizontal="right")
        for c in range(8, 13):
            ws.cell(i, c).border = Border(bottom=line)
    if not changes[changes["change"] == "Price down"].empty:
        best = changes[changes["change"] == "Price down"].iloc[0]
        ws.cell(35, 8, "Biggest price drop:").font = Font(size=9, bold=True, color=GREY)
        ws.cell(36, 8, f"{best['title'][:45]}  £{best['old_price']:.2f} → £{best['new_price']:.2f} "
                       f"({best['diff_pct']:+.0%})").font = Font(size=9, color=GREEN)


def _notes_sheet(ws, df, scraped_at, source, previous_label) -> None:
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 100
    ws["A1"] = "About this report"
    ws["A1"].font = Font(size=16, bold=True, color=NAVY)
    rows = [
        ("Source", source),
        ("Scraped at", f"{scraped_at:%d %B %Y, %H:%M}"),
        ("Product count", f"{len(df):,} (duplicates removed by UPC)"),
        ("Compared with", previous_label or "nothing (first run)"),
        ("Method", "Every catalogue page and every product page was visited. Requests are spaced out "
                   "and retried automatically, so the site is never overloaded."),
        ("How to refresh", "Double-click run.bat. Each run saves a snapshot and compares it with the previous one."),
        ("", ""),
        ("Sheet: Summary", "Key numbers and charts."),
        ("Sheet: Products", "One row per product, with filters on every column. Click 'Open ↗' to see the product page."),
        ("Sheet: Categories", "Count, average/min/max price, rating and stock per category."),
        ("Sheet: Price changes", "Prices that went up or down, stock changes, and new or removed products since the last run."),
        ("", ""),
        ("Prepared by", "Umut Doruk Öztürk · Python automation & web data extraction"),
    ]
    for r, (key, value) in enumerate(rows, start=3):
        ws.cell(r, 1, key).font = Font(bold=True, color=NAVY)
        cell = ws.cell(r, 2, value)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(r, 1).alignment = Alignment(vertical="top")
