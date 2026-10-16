import asyncio, json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sales_mcp as s  # noqa: E402


class ServerIdentityTest(unittest.TestCase):
    def test_server_info_reports_package_identity_not_library_version(self):
        server = s.make_server(adapter=None)
        low = server._mcp_server
        manifest = json.loads((ROOT / 'manifest.json').read_text())
        self.assertEqual(low.name, 'noticer')
        self.assertEqual(low.version, manifest['version'])
        self.assertNotEqual(low.version, '1.29.0')
        opts = low.create_initialization_options()
        self.assertEqual(opts.server_name, 'noticer')
        self.assertEqual(opts.server_version, manifest['version'])

    def test_tools_unchanged(self):
        server = s.make_server(adapter=None)
        names = sorted(t.name for t in asyncio.run(server.list_tools()))
        self.assertIn('noticer_prepare_receipt', names)
        self.assertIn('noticer_get_verified_receipt', names)

    def test_version_falls_back_to_version_file(self):
        self.assertTrue(s.package_version())


if __name__ == '__main__':
    unittest.main()


class OneVersionStringTest(unittest.TestCase):
    def test_manifest_version_is_the_single_release_string(self):
        manifest = json.loads((ROOT / 'manifest.json').read_text())['version']
        self.assertEqual(manifest, '0.3.2-dev.20261016')
        self.assertEqual(s.make_server(adapter=None)._mcp_server.version, manifest)
        # Python packaging needs the PEP 440 spelling of the same version.
        self.assertEqual((ROOT / 'VERSION').read_text().strip(), '0.3.2.dev20261016')
        self.assertIn('version = "0.3.2.dev20261016"', (ROOT / 'pyproject.toml').read_text())
        server_json = json.loads((ROOT.parent / 'server.json').read_text())
        self.assertEqual(server_json['version'], manifest)
        self.assertEqual(server_json['packages'][0]['version'], manifest)

    def test_manifest_sha256_matches_every_listed_file(self):
        import hashlib
        for line in (ROOT / 'MANIFEST.sha256').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)
