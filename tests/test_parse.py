from price_scraper.parse import parse_listing, parse_price, parse_product, parse_stock

LISTING = """
<ol>
  <li><article class="product_pod"><h3><a href="book-one_1/index.html" title="Book One">Book One</a></h3></article></li>
  <li><article class="product_pod"><h3><a href="book-two_2/index.html" title="Book Two">Book Two</a></h3></article></li>
</ol>
<ul class="pager"><li class="next"><a href="page-2.html">next</a></li></ul>
"""

PRODUCT = """
<ul class="breadcrumb"><li>Home</li><li>Books</li><li>Poetry</li><li>Book One</li></ul>
<div id="product_gallery"><img src="../../media/cover.jpg"></div>
<div class="product_main">
  <h1>Book One</h1>
  <p class="star-rating Four"></p>
</div>
<div id="product_description"><h2>Product Description</h2></div>
<p>A lovely book.</p>
<table class="table table-striped">
  <tr><th>UPC</th><td>abc123</td></tr>
  <tr><th>Price (excl. tax)</th><td>£51.77</td></tr>
  <tr><th>Price (incl. tax)</th><td>£51.77</td></tr>
  <tr><th>Availability</th><td>In stock (22 available)</td></tr>
  <tr><th>Number of reviews</th><td>3</td></tr>
</table>
"""


def test_parse_price():
    assert parse_price("£51.77") == 51.77
    assert parse_price("£1,234.50") == 1234.50
    assert parse_price("free") is None


def test_parse_stock():
    assert parse_stock("In stock (22 available)") == 22
    assert parse_stock("Out of stock") == 0


def test_parse_listing_returns_absolute_links_and_next_page():
    links, next_url = parse_listing(LISTING, "https://books.toscrape.com/catalogue/page-1.html")
    assert links == [
        "https://books.toscrape.com/catalogue/book-one_1/index.html",
        "https://books.toscrape.com/catalogue/book-two_2/index.html",
    ]
    assert next_url == "https://books.toscrape.com/catalogue/page-2.html"


def test_parse_listing_last_page_has_no_next():
    _, next_url = parse_listing("<ol></ol>", "https://example.com/page-50.html")
    assert next_url is None


def test_parse_product():
    url = "https://books.toscrape.com/catalogue/book-one_1/index.html"
    record = parse_product(PRODUCT, url)
    assert record["title"] == "Book One"
    assert record["category"] == "Poetry"
    assert record["price"] == 51.77
    assert record["rating"] == 4
    assert record["stock"] == 22
    assert record["reviews"] == 3
    assert record["upc"] == "abc123"
    assert record["description"] == "A lovely book."
    assert record["image_url"] == "https://books.toscrape.com/media/cover.jpg"
