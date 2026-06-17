"""Dynamic OpenGraph share page + on-the-fly OG image (MEMO §3)."""


def test_share_page_has_og_tags(client, auth_headers):
    headers = auth_headers("frank")
    client.post("/api/profile/solve", headers=headers, json={"difficulty": "hard"})

    res = client.get("/user/frank")
    assert res.status_code == 200
    assert res.mimetype == "text/html"
    html = res.get_data(as_text=True)
    for tag in ('property="og:title"', 'property="og:description"',
                'property="og:image"', 'property="og:url"',
                'name="twitter:card"'):
        assert tag in html
    assert "frank" in html
    assert "/api/og-image?" in html          # points at the dynamic image


def test_share_page_404(client):
    assert client.get("/user/ghost").status_code == 404


def test_og_image_renders_svg(client):
    res = client.get("/api/og-image?user=frank&rank=1450&solved=42&badge=DbExpert")
    assert res.status_code == 200
    assert res.mimetype == "image/svg+xml"
    svg = res.get_data(as_text=True)
    assert svg.lstrip().startswith("<svg")
    assert "1450" in svg and "42" in svg and "DbExpert" in svg
    assert "frank" in svg


def test_og_image_escapes_params(client):
    # a hostile param must not break out of the SVG text node
    res = client.get("/api/og-image?user=<script>alert(1)</script>")
    body = res.get_data(as_text=True)
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
