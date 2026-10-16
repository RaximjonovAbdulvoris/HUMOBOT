import sqlite3
import unittest
from cryptography.fernet import Fernet, InvalidToken
from scripts.backup_test_state import pack, unpack


class BackupTests(unittest.TestCase):
    def files(self):
        key = Fernet.generate_key()
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE sequence (id INTEGER PRIMARY KEY AUTOINCREMENT)')
            db.execute('INSERT INTO sequence DEFAULT VALUES')
            content = db.serialize()
        return {'.env.test': b'TEST_ONLY=1\n', 'bot_persistence.key': key,
            'bot_persistence.pkl': b'HUMOENC1\n' + Fernet(key).encrypt(b'trusted-state-test'),
            'application_numbers.sqlite3': content}

    def test_roundtrip_authenticates_state_key_and_counter_without_unpickling(self):
        files = self.files()
        encrypted = pack(files, 'fictional-test-passphrase')
        self.assertNotIn(files['bot_persistence.key'], encrypted)
        self.assertEqual(unpack(encrypted, 'fictional-test-passphrase'), files)
        with self.assertRaises(InvalidToken):
            unpack(encrypted, 'wrong-test-passphrase')

    def test_wrong_state_key_and_unknown_backup_paths_are_rejected(self):
        files = self.files()
        files['bot_persistence.key'] = Fernet.generate_key()
        with self.assertRaises(InvalidToken):
            pack(files, 'fictional-test-passphrase')
        files = self.files()
        files['../unsafe'] = b'test'
        with self.assertRaises(ValueError):
            pack(files, 'fictional-test-passphrase')
