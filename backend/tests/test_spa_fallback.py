"""Regression tests for the Flask-served Svelte SPA fallback."""

from http import HTTPStatus


def test_extensionless_report_route_uses_spa_fallback(client, app, monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<main>bgmon SPA</main>")
    monkeypatch.setattr(app, "static_folder", str(tmp_path))

    response = client.get("/report")

    assert response.status_code == HTTPStatus.OK
    assert response.data == b"<main>bgmon SPA</main>"


def test_missing_asset_and_api_path_do_not_use_spa_fallback(client, app, monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<main>bgmon SPA</main>")
    monkeypatch.setattr(app, "static_folder", str(tmp_path))

    assert client.get("/missing.js").status_code == HTTPStatus.NOT_FOUND
    assert client.get("/api").status_code == HTTPStatus.NOT_FOUND
    assert client.get("/api/not-a-real-resource").status_code == HTTPStatus.NOT_FOUND
