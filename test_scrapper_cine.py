import tempfile
import sys
import types
import unittest
import os
from pathlib import Path
from unittest.mock import patch

telegram = types.ModuleType("telegram")
telegram.Update = object
telegram.Bot = object
telegram_ext = types.ModuleType("telegram.ext")
telegram_ext.ApplicationBuilder = object
telegram_ext.CommandHandler = object
telegram_ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
telegram_error = types.ModuleType("telegram.error")
telegram_error.TelegramError = Exception
sys.modules.setdefault("telegram", telegram)
sys.modules.setdefault("telegram.ext", telegram_ext)
sys.modules.setdefault("telegram.error", telegram_error)

secrets_file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
secrets_file.write("{'chatNacho': 1, 'chatPibes': 2, 'botToken2': 'test'}")
secrets_file.close()
os.environ["SCRAPPER_SECRETS_FILE"] = secrets_file.name

import scrapper_cine


class ScrapperCineTests(unittest.TestCase):
    def test_tree_cinema_id_uses_ewave_id_except_for_imax(self):
        cinemas = scrapper_cine.active_cinemas([
            {"id": 18, "ciN_Name": "IMAX Theatre (Norcenter)", "ciN_EwaveId": 3204, "ciN_Active": True},
            {"id": 19, "ciN_Name": "Cine común", "ciN_EwaveId": 3208, "ciN_Active": True},
            {"id": 20, "ciN_Name": "Cine cerrado", "ciN_Active": False},
        ])

        self.assertEqual(scrapper_cine.tree_cinema_id(cinemas["18"]), "3250")
        self.assertEqual(scrapper_cine.tree_cinema_id(cinemas["19"]), "3208")
        self.assertNotIn("3250", cinemas)
        self.assertNotIn("20", cinemas)

    def test_normalize_showtimes_ignores_performance_ids_and_sorts(self):
        normalized = scrapper_cine.normalize_showtimes({
            "days": {
                "2026-09-05": [{
                    "formats": [{
                        "formatDescription": "IMAX-Subtitulado",
                        "performances": [
                            {"performanceId": 2, "showTime": "15:25"},
                            {"performanceId": 1, "showTime": "12:00"},
                            {"performanceId": 3, "showTime": "15:25"},
                        ],
                    }],
                }],
            },
        })

        self.assertEqual(normalized, {
            "2026-09-05": [
                {"format": "IMAX-Subtitulado", "time": "12:00"},
                {"format": "IMAX-Subtitulado", "time": "15:25"},
            ],
        })

    def test_showtime_changes_returns_added_and_removed_items(self):
        previous = {"2026-09-05": [{"format": "2D", "time": "12:00"}]}
        current = {"2026-09-05": [{"format": "2D", "time": "15:00"}]}

        self.assertEqual(
            scrapper_cine.showtime_changes(previous, current),
            (["2026-09-05 2D 15:00"], ["2026-09-05 2D 12:00"]),
        )

    def test_initial_schedule_message_includes_days_times_and_format(self):
        message = scrapper_cine.format_initial_schedule_message(
            {"name": "La Odisea"},
            {"ciN_Name": "IMAX Theatre (Norcenter)"},
            {"2026-09-05": [{"format": "IMAX-Subtitulado", "time": "12:00"}]},
        )

        self.assertIn("2026-09-05:", message)
        self.assertIn("12:00 (IMAX-Subtitulado)", message)

    def test_state_is_saved_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "cine_state.json"
            state = scrapper_cine.default_state()
            state["selected_films"] = ["5875"]
            with patch.object(scrapper_cine, "STATE_FILE", state_path):
                scrapper_cine.save_state(state)
                self.assertEqual(scrapper_cine.load_state()["selected_films"], ["5875"])
                self.assertEqual(list(Path(directory).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()