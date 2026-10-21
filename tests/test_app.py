import os
import unittest
from datetime import date
from unittest.mock import Mock, patch

import app
from streamlit.testing.v1 import AppTest


class FinanceHelpersTest(unittest.TestCase):
    def test_amount_is_stored_as_integer_cents(self):
        self.assertEqual(app.amount_to_cents(1234.56), 123456)

    def test_amount_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "maior que zero"):
            app.amount_to_cents(0)

    def test_brl_amount_uses_brazilian_format(self):
        self.assertEqual(app.format_brl(123456), "R$ 1.234,56")

    def test_transaction_data_trims_description_and_uses_uid(self):
        transaction = app._transaction_data(
            owner_uid="firebase-uid",
            description="  Mercado  ",
            transaction_type="expense",
            amount=75.9,
            transaction_date=date(2026, 10, 15),
        )
        self.assertEqual(transaction["owner_uid"], "firebase-uid")
        self.assertEqual(transaction["description"], "Mercado")
        self.assertEqual(transaction["amount_cents"], 7590)
        self.assertEqual(transaction["type"], "expense")


class FirebaseAuthenticationTest(unittest.TestCase):
    @patch.dict(os.environ, {"FIREBASE_API_KEY": "test-api-key"})
    @patch("app.requests.post")
    def test_authentication_returns_only_user_identity(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "localId": "user-123",
            "email": "user@example.com",
            "idToken": "must-not-be-returned",
            "refreshToken": "must-not-be-returned",
        }
        post.return_value = response

        user = app.authenticate("user@example.com", "password1", register=False)

        self.assertEqual(user, {"uid": "user-123", "email": "user@example.com"})
        self.assertIn("signInWithPassword", post.call_args.args[0])

    @patch.dict(os.environ, {"FIREBASE_API_KEY": "test-api-key"})
    @patch("app.requests.post")
    def test_authentication_translates_firebase_error(self, post):
        response = Mock()
        response.ok = False
        response.json.return_value = {"error": {"message": "EMAIL_EXISTS"}}
        post.return_value = response

        with self.assertRaisesRegex(app.FirebaseAuthError, "já está cadastrado"):
            app.authenticate("user@example.com", "password1", register=True)


class GeminiFinancialAnalysisTest(unittest.TestCase):
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"})
    @patch("app.requests.post")
    def test_analysis_uses_stateless_gemini_request_without_account_identity(self, post):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "steps": [
                {"type": "thought", "text": "Este conteúdo não deve ser exibido."},
                {
                    "type": "model_output",
                    "content": [
                        {"type": "text", "text": "Suas despesas estão estáveis."}
                    ],
                },
            ]
        }
        post.return_value = response
        transactions = [
            {
                "id": "private-document-id",
                "owner_uid": "private-user-id",
                "type": "income",
                "amount_cents": 250000,
                "date": date(2026, 10, 1),
                "description": "Salário",
            },
            {
                "id": "another-private-document-id",
                "owner_uid": "private-user-id",
                "type": "expense",
                "amount_cents": 40000,
                "date": date(2026, 10, 5),
                "description": "Mercado",
            },
        ]

        result = app.analyze_finances(transactions)

        self.assertEqual(result, "Suas despesas estão estáveis.")
        self.assertNotIn("conteúdo não deve ser exibido", result)
        self.assertEqual(
            post.call_args.args[0], app.GEMINI_INTERACTIONS_URL
        )
        self.assertEqual(
            post.call_args.kwargs["headers"],
            {"x-goog-api-key": "test-gemini-key"},
        )
        request_body = post.call_args.kwargs["json"]
        self.assertEqual(request_body["model"], app.GEMINI_MODEL)
        self.assertFalse(request_body["store"])
        self.assertNotIn("private-user-id", request_body["input"])
        self.assertNotIn("private-document-id", request_body["input"])
        self.assertIn("Salário", request_body["input"])

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"})
    @patch("app.requests.post")
    def test_invalid_gemini_key_returns_configuration_error(self, post):
        response = Mock()
        response.ok = False
        response.status_code = 403
        post.return_value = response

        with self.assertRaisesRegex(
            app.GeminiConfigurationError, "recusou a chave configurada"
        ):
            app.analyze_finances(
                [
                    {
                        "type": "expense",
                        "amount_cents": 100,
                        "date": date(2026, 10, 5),
                        "description": "Café",
                    }
                ]
            )

    @patch("app.requests.post")
    def test_empty_transactions_do_not_call_gemini(self, post):
        with self.assertRaisesRegex(app.GeminiAnalysisError, "ao menos um lançamento"):
            app.analyze_finances([])
        post.assert_not_called()


class AuthenticationScreenTest(unittest.TestCase):
    def test_signup_rejects_mismatched_passwords(self):
        test_app = AppTest.from_file(str(app.APP_DIR / "app.py")).run()
        test_app.segmented_control[0].set_value("Criar conta")
        test_app.run()
        test_app.text_input[0].set_value("user@example.com")
        test_app.text_input[1].set_value("password1")
        test_app.text_input[2].set_value("password2")
        test_app.form_submit_button[0].click()
        test_app.run()

        self.assertEqual(test_app.error[0].value, "As senhas não conferem.")


def _render_dashboard_with_fake_transactions():
    from datetime import datetime, timezone

    import app

    class Snapshot:
        def __init__(self, item_id, data):
            self.id = item_id
            self.data = data

        def to_dict(self):
            return self.data

    class Collection:
        def collection(self, _name):
            return self

        def where(self, *_args):
            return self

        def stream(self):
            transaction_date = datetime.now(timezone.utc)
            return iter(
                [
                    Snapshot(
                        "income-1",
                        {
                            "type": "income",
                            "amount_cents": 250000,
                            "date": transaction_date,
                            "description": "Salário",
                        },
                    ),
                    Snapshot(
                        "expense-1",
                        {
                            "type": "expense",
                            "amount_cents": 12500,
                            "date": transaction_date,
                            "description": "Mercado",
                        },
                    ),
                ]
            )

    app._render_dashboard(Collection(), "test-user")


class DashboardScreenTest(unittest.TestCase):
    def test_dashboard_renders_transactions_and_mobile_navigation(self):
        test_app = AppTest.from_function(
            _render_dashboard_with_fake_transactions
        ).run()

        self.assertEqual(len(test_app.exception), 0)
        button_keys = {button.key for button in test_app.button}
        self.assertTrue(
            {
                "edit_income-1",
                "delete_income-1",
                "edit_expense-1",
                "delete_expense-1",
                "financial_analysis_button",
                "mobile_nav_home",
                "mobile_nav_add",
                "mobile_nav_palette",
                "mobile_nav_logout",
            }.issubset(button_keys)
        )

    def test_financial_analysis_button_opens_dialog(self):
        test_app = AppTest.from_function(
            _render_dashboard_with_fake_transactions
        ).run()
        analysis_button = [
            button
            for button in test_app.button
            if button.key == "financial_analysis_button"
        ][0]
        analysis_button.click()
        test_app.run()

        self.assertEqual(len(test_app.exception), 0)
        self.assertTrue(
            any(button.key == "generate_financial_analysis" for button in test_app.button)
        )


if __name__ == "__main__":
    unittest.main()
