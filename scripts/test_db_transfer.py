"""Standalone tests: deliberately outside tests/conftest.py's destructive seed."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from db_transfer import check_empty, differences, digest, prepare_neon


class RestoreGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.uri = self.root / "connection.url"
        self.service = self.root / "service.conf"
        self.host = "ep-approved.aws.neon.tech"

    def credentials(self, uri=None, mode=0o600):
        self.uri.write_text(uri or f"postgresql://owner:synthetic-secret@{self.host}/neondb?sslmode=require&channel_binding=require")
        self.uri.chmod(mode)

    def test_tls_is_strengthened_and_secret_file_is_private(self):
        self.credentials()
        prepare_neon(self.uri,self.service,self.host)
        self.assertIn("sslmode=verify-full",self.service.read_text())
        self.assertEqual(self.service.stat().st_mode & 0o777,0o600)

    def test_unapproved_endpoint_refused(self):
        self.credentials("postgresql://owner:synthetic@ep-other.aws.neon.tech/neondb")
        with self.assertRaises(ValueError):
            prepare_neon(self.uri,self.service,self.host)
        self.assertFalse(self.service.exists())

    def test_pooler_refused_for_restore(self):
        host = "ep-approved-pooler.aws.neon.tech"
        self.credentials(f"postgresql://owner:synthetic@{host}/neondb")
        with self.assertRaises(ValueError):
            prepare_neon(self.uri,self.service,host)

    def test_world_readable_secret_refused(self):
        self.credentials(mode=0o644)
        with self.assertRaises(ValueError):
            prepare_neon(self.uri,self.service,self.host)

    def test_service_option_injection_refused(self):
        self.credentials(f"postgresql://owner:secret%0Asslmode%3Ddisable@{self.host}/neondb")
        with self.assertRaises(ValueError):
            prepare_neon(self.uri,self.service,self.host)

    def test_unknown_options_refused(self):
        self.credentials(f"postgresql://owner:synthetic@{self.host}/neondb?options=unexpected")
        with self.assertRaises(ValueError):
            prepare_neon(self.uri,self.service,self.host)

    def test_existing_credential_not_rotated(self):
        self.credentials()
        self.service.write_text("keep-existing-credential")
        with self.assertRaises(ValueError):
            prepare_neon(self.uri,self.service,self.host)
        self.assertEqual(self.service.read_text(),"keep-existing-credential")

    def test_nonempty_database_refused_without_sql_mutation(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"count":1}
        with self.assertRaises(ValueError):
            check_empty(conn)
        self.assertEqual(cursor.execute.call_count,1)
        self.assertTrue(cursor.execute.call_args.args[0].lstrip().startswith("SELECT"))

    def test_row_content_changes_detected_even_with_same_counts(self):
        original = {k:{} for k in ("tables","columns","constraints","indexes","sequences","searches")}
        original["tables"]={"human_reviews":{"rows":1,"sha256":digest({"decision":"ACCEPT"})}}
        changed = {**original,"tables":{"human_reviews":{"rows":1,"sha256":digest({"decision":"REJECT"})}}}
        self.assertEqual(differences(original,changed),["tables"])


if __name__ == "__main__":
    unittest.main()
