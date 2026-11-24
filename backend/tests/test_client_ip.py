import unittest
from types import SimpleNamespace

from services.client_ip import client_ip


def req(peer, headers=None):
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers={k.lower(): v for k, v in (headers or {}).items()})


class ClientIpTests(unittest.TestCase):
    def test_private_peer_uses_real_ip_header(self):
        self.assertEqual(client_ip(req("172.18.0.3", {"X-Real-IP": "1.2.3.4"})), "1.2.3.4")

    def test_public_peer_cannot_forge_header(self):
        self.assertEqual(client_ip(req("8.8.8.8", {"X-Real-IP": "1.2.3.4"})), "8.8.8.8")

    def test_invalid_header_falls_back_to_peer(self):
        self.assertEqual(client_ip(req("10.0.0.2", {"X-Real-IP": "not-an-ip"})), "10.0.0.2")

    def test_missing_client(self):
        self.assertEqual(client_ip(SimpleNamespace(client=None, headers={})), "unknown")


if __name__ == "__main__":
    unittest.main()
