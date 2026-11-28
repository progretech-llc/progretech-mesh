"""Crawlers discover public documentation without gaining console access."""
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

from main import create_app


def test_public_discovery_preserves_private_boundary(monkeypatch):
    monkeypatch.setenv('DEV_SEED_AGENTS', '0')
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        sitemap = client.get('/sitemap.xml', headers={'Host': 'untrusted.example'})
        assert sitemap.status_code == 200
        assert sitemap.mimetype == 'application/xml'
        locations = [node.text for node in ElementTree.fromstring(sitemap.data).iter()
                     if node.tag.endswith('}loc')]
        assert locations == ['https://mesh.progretech.com/how-it-works']
        assert client.get('/how-it-works').status_code == 200
        assert client.get('/').status_code in (302, 303)
        robots = client.get('/robots.txt')
        assert robots.status_code == 200
        policy = RobotFileParser()
        policy.parse(robots.get_data(as_text=True).splitlines())
        assert policy.can_fetch('Googlebot', '/how-it-works')
        for path in ['/api/session', '/agents/example/task-board', '/login',
                     '/auth/callback', '/factory/tasks', '/static/analytics/analytics-frame.html']:
            assert not policy.can_fetch('Googlebot', path)
        assert policy.site_maps() == ['https://mesh.progretech.com/sitemap.xml']
