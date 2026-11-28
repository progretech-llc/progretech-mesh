"""The optional measurement frame is the only Mesh document permitting Google script."""
from main import create_app


def test_measurement_frame_has_narrow_network_policy(monkeypatch):
    monkeypatch.setenv('DEV_SEED_AGENTS', '0')
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        frame = client.get('/static/analytics/analytics-frame.html')
        login = client.get('/login')
    assert frame.status_code == 200
    assert frame.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert frame.headers['Referrer-Policy'] == 'no-referrer'
    assert 'https://www.googletagmanager.com' in frame.headers['Content-Security-Policy']
    assert "frame-ancestors 'self'" in frame.headers['Content-Security-Policy']
    assert 'googletagmanager' not in login.headers['Content-Security-Policy']
    assert login.headers['X-Frame-Options'] == 'DENY'
