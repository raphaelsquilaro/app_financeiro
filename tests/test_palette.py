import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import app
import palette


class PaletteLogicTest(unittest.TestCase):
    def test_default_palette_has_all_expected_keys(self):
        loaded = palette.DEFAULT_PALETTE
        expected_keys = {
            "primaryColor",
            "backgroundColor",
            "secondaryBackgroundColor",
            "textColor",
            "incomeColor",
            "expenseColor",
            "font",
        }
        self.assertTrue(expected_keys.issubset(loaded.keys()))

    def test_save_and_load_palette_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            tmp_json = tmp_path / "palette.json"
            tmp_toml = tmp_path / "config.toml"

            with patch.object(palette, "PALETTE_FILE", tmp_json), patch.object(
                palette, "CONFIG_PATH", tmp_toml
            ):
                custom = dict(palette.DEFAULT_PALETTE)
                custom["primaryColor"] = "#ff007f"
                custom["incomeColor"] = "#00aa00"

                palette.save_palette(custom, preset_name="Test Preset")

                self.assertTrue(tmp_json.is_file())
                self.assertTrue(tmp_toml.is_file())

                loaded = palette.load_palette()
                self.assertEqual(loaded["primaryColor"], "#ff007f")
                self.assertEqual(loaded["incomeColor"], "#00aa00")

                # Confira o TOML
                toml_content = tmp_toml.read_text(encoding="utf-8")
                self.assertIn("[theme]", toml_content)
                self.assertIn('primaryColor = "#ff007f"', toml_content)

    def test_load_palette_falls_back_to_config_toml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            tmp_json = tmp_path / "non_existent.json"
            tmp_toml = tmp_path / "config.toml"
            tmp_toml.write_text(
                '[theme]\nprimaryColor = "#112233"\nbackgroundColor = "#445566"\n',
                encoding="utf-8",
            )

            with patch.object(palette, "PALETTE_FILE", tmp_json), patch.object(
                palette, "CONFIG_PATH", tmp_toml
            ):
                loaded = palette.load_palette()
                self.assertEqual(loaded["primaryColor"], "#112233")
                self.assertEqual(loaded["backgroundColor"], "#445566")
                # incomeColor usa o padrão
                self.assertEqual(
                    loaded["incomeColor"], palette.DEFAULT_PALETTE["incomeColor"]
                )

    def test_find_matching_preset(self):
        emerald = dict(palette.PALETTE_PRESETS["🌿 Verde Esmeralda (Padrão)"])
        self.assertEqual(
            palette._find_matching_preset(emerald), "🌿 Verde Esmeralda (Padrão)"
        )

        custom = dict(emerald)
        custom["primaryColor"] = "#999999"
        self.assertEqual(palette._find_matching_preset(custom), "✨ Personalizado")

    def test_build_theme_css_contains_variables(self):
        css = palette.build_theme_css(palette.DEFAULT_PALETTE)
        self.assertIn("--primary-color: #16856b;", css)
        self.assertIn("--finance-income: #16856b;", css)
        self.assertIn("--finance-expense: #d32f2f;", css)
        self.assertIn(".stApp", css)


class PaletteScreenAppTest(unittest.TestCase):
    def test_palette_screen_renders_and_allows_preset_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            tmp_json = tmp_path / "palette.json"
            tmp_toml = tmp_path / "config.toml"

            with patch.object(palette, "PALETTE_FILE", tmp_json), patch.object(
                palette, "CONFIG_PATH", tmp_toml
            ):
                test_app = AppTest.from_file(str(app.APP_DIR / "app.py"))
                test_app.session_state["page"] = "palette"
                test_app.run()

                # Verifica que o título da tela de paleta foi renderizado
                self.assertTrue(
                    any("Paleta de cores" in str(title.value) for title in test_app.title)
                )

                # Verifica seletores de cores
                self.assertGreaterEqual(len(test_app.color_picker), 6)

                # Seleciona o tema "🌌 Modo Noturno / Dark"
                dark_preset = "🌌 Modo Noturno / Dark"
                test_app.selectbox[0].select(dark_preset)
                test_app.run()

                # Cores devem refletir o preset escuro (#818cf8 no primaryColor)
                primary_picker = [
                    cp for cp in test_app.color_picker if cp.key == "palette_primaryColor"
                ][0]
                self.assertEqual(
                    primary_picker.value,
                    palette.PALETTE_PRESETS[dark_preset]["primaryColor"],
                )

                # Clica em salvar
                save_btn = [b for b in test_app.button if b.key == "save_palette_btn"][0]
                save_btn.click()
                test_app.run()

                # Arquivos devem ter sido persistidos
                self.assertTrue(tmp_json.is_file())
                saved_json = json.loads(tmp_json.read_text(encoding="utf-8"))
                self.assertEqual(
                    saved_json["primaryColor"],
                    palette.PALETTE_PRESETS[dark_preset]["primaryColor"],
                )

    def test_restore_default_palette_button(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            tmp_json = tmp_path / "palette.json"
            tmp_toml = tmp_path / "config.toml"

            with patch.object(palette, "PALETTE_FILE", tmp_json), patch.object(
                palette, "CONFIG_PATH", tmp_toml
            ):
                test_app = AppTest.from_file(str(app.APP_DIR / "app.py"))
                test_app.session_state["page"] = "palette"
                test_app.run()

                # Clica em restaurar padrão
                reset_btn = [
                    b for b in test_app.button if b.key == "reset_palette_btn"
                ][0]
                reset_btn.click()
                test_app.run()

                primary_picker = [
                    cp for cp in test_app.color_picker if cp.key == "palette_primaryColor"
                ][0]
                self.assertEqual(
                    primary_picker.value, palette.DEFAULT_PALETTE["primaryColor"]
                )

    def test_navigation_from_auth_to_palette_and_back(self):
        test_app = AppTest.from_file(str(app.APP_DIR / "app.py")).run()
        # Na tela de autenticação, o botão auth_palette_btn deve estar presente
        auth_palette_btn = [b for b in test_app.button if b.key == "auth_palette_btn"][0]
        auth_palette_btn.click()
        test_app.run()

        # Agora deve estar na tela de paleta
        self.assertEqual(test_app.session_state["page"], "palette")
        self.assertTrue(any("Paleta de cores" in str(title.value) for title in test_app.title))

        # Clica em Voltar pelo botão cancel_palette_btn
        cancel_btn = [b for b in test_app.button if b.key == "cancel_palette_btn"][0]
        cancel_btn.click()
        test_app.run()

        # Deve voltar para a tela inicial/dashboard (que renderiza auth quando deslogado)
        self.assertEqual(test_app.session_state["page"], "dashboard")
        self.assertEqual(test_app.title[0].value, "Meu financeiro")

    def test_top_back_button_returns_to_dashboard(self):
        test_app = AppTest.from_file(str(app.APP_DIR / "app.py"))
        test_app.session_state["page"] = "palette"
        test_app.run()

        top_back = [b for b in test_app.button if b.key == "palette_top_back"][0]
        top_back.click()
        test_app.run()

        self.assertEqual(test_app.session_state["page"], "dashboard")

    def test_manual_color_change_saves_custom_preset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            tmp_json = tmp_path / "palette.json"
            tmp_toml = tmp_path / "config.toml"

            with patch.object(palette, "PALETTE_FILE", tmp_json), patch.object(
                palette, "CONFIG_PATH", tmp_toml
            ):
                test_app = AppTest.from_file(str(app.APP_DIR / "app.py"))
                test_app.session_state["page"] = "palette"
                test_app.run()

                # Altera manualmente o color picker de receita
                income_picker = [
                    cp for cp in test_app.color_picker if cp.key == "palette_incomeColor"
                ][0]
                income_picker.set_value("#129934")
                test_app.run()

                save_btn = [b for b in test_app.button if b.key == "save_palette_btn"][0]
                save_btn.click()
                test_app.run()

                self.assertTrue(tmp_json.is_file())
                saved = json.loads(tmp_json.read_text(encoding="utf-8"))
                self.assertEqual(saved["incomeColor"], "#129934")


if __name__ == "__main__":
    unittest.main()
