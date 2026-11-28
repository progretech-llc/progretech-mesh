import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class TestPrivateLanAcceptanceTransport(unittest.TestCase):
    def test_plugin_allows_private_lan_http_but_rejects_public_http(self):
        s=(ROOT/'openclaw-plugin-progretech-mesh/index.js').read_text()
        self.assertIn('isPrivateLanHostname',s)
        self.assertIn('parts[0] === 192 && parts[1] === 168',s)
        self.assertIn('parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31',s)
        self.assertIn('url.protocol === "http:" && !isPrivateLanHostname(url.hostname)',s)
        self.assertIn('mesh_https_required',s)

    def test_bootstrap_allows_rfc1918_package_sources(self):
        s=(ROOT/'distribution/openclaw-self-bootstrap-v1.sh').read_text()
        for marker in ('http://10.*','http://192.168.*','http://172.1[6-9].*','private-LAN'):
            self.assertIn(marker,s)

    def test_python_package_stager_is_private_lan_only_for_http(self):
        s=(ROOT/'install/mesh_plugin_package.py').read_text()
        self.assertIn('ipaddress.ip_address(host).is_private',s)
        self.assertIn('HTTP Mesh plugin package URL is allowed only for loopback/private-LAN hosts',s)

    def test_production_origin_still_requires_https(self):
        s=(ROOT/'main.py').read_text()
        self.assertIn('production_mesh_public_origin_requires_https',s)

if __name__=='__main__': unittest.main()
