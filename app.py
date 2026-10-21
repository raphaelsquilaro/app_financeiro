from __future__ import annotations

import os
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import firebase_admin
import requests
import streamlit as st
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import GoogleAuthError
from streamlit.errors import StreamlitSecretNotFoundError

from palette import (
    DEFAULT_PALETTE,
    apply_palette_css,
    hex_to_rgba,
    load_palette,
    render_palette_screen,
)


APP_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = (
    "app-financeiro-9a5ae-firebase-adminsdk-fbsvc-b340319d7a.json"
)
TRANSACTIONS_COLLECTION = "transactions"
AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts"


class FirebaseConfigurationError(RuntimeError):
    pass


class FirebaseAuthError(RuntimeError):
    pass


def _firebase_secrets() -> dict[str, Any]:
    try:
        return dict(st.secrets.get("firebase", {}))
    except StreamlitSecretNotFoundError:
        return {}


def _configured_value(secret_name: str, environment_name: str) -> str | None:
    value = os.environ.get(environment_name) or _firebase_secrets().get(secret_name)
    return str(value).strip() if value else None


def _credentials_path() -> Path:
    configured_path = _configured_value(
        "admin_credentials_path", "FIREBASE_CREDENTIALS_PATH"
    )
    path = Path(configured_path) if configured_path else APP_DIR / CREDENTIALS_FILE
    return path if path.is_absolute() else APP_DIR / path


def _firebase_api_key() -> str:
    api_key = _configured_value("api_key", "FIREBASE_API_KEY")
    if not api_key or api_key == "COLE_A_WEB_API_KEY_AQUI":
        raise FirebaseConfigurationError(
            "Configure a Web API Key em .streamlit/secrets.toml "
            "ou na variável FIREBASE_API_KEY."
        )
    return api_key


@st.cache_resource
def get_firestore_client() -> firestore.Client:
    admin_credentials = _firebase_secrets().get("admin_credentials")
    if admin_credentials:
        firebase_credential = credentials.Certificate(dict(admin_credentials))
    else:
        credential_path = _credentials_path()
        if not credential_path.is_file():
            raise FirebaseConfigurationError(
                "Configure firebase.admin_credentials nos Secrets do Streamlit "
                "ou disponibilize o arquivo JSON de credenciais local."
            )
        firebase_credential = credentials.Certificate(str(credential_path))

    try:
        app = firebase_admin.get_app("app_financeiro")
    except ValueError:
        app = firebase_admin.initialize_app(
            firebase_credential, name="app_financeiro"
        )

    return firestore.client(app=app)


def _auth_error_message(code: str) -> str:
    messages = {
        "EMAIL_EXISTS": "Este e-mail já está cadastrado.",
        "INVALID_EMAIL": "Informe um e-mail válido.",
        "WEAK_PASSWORD": "A senha precisa ter pelo menos 6 caracteres.",
        "EMAIL_NOT_FOUND": "E-mail ou senha inválidos.",
        "INVALID_PASSWORD": "E-mail ou senha inválidos.",
        "INVALID_LOGIN_CREDENTIALS": "E-mail ou senha inválidos.",
        "USER_DISABLED": "Esta conta foi desativada.",
        "TOO_MANY_ATTEMPTS_TRY_LATER": (
            "Muitas tentativas. Aguarde um pouco e tente novamente."
        ),
        "API_KEY_INVALID": "A Web API Key do Firebase é inválida.",
        "OPERATION_NOT_ALLOWED": (
            "Ative o provedor E-mail/senha em Authentication no Firebase."
        ),
    }
    return messages.get(code, "Não foi possível autenticar. Verifique a configuração.")


def authenticate(email: str, password: str, *, register: bool) -> dict[str, str]:
    api_key = _firebase_api_key()
    operation = "signUp" if register else "signInWithPassword"
    url = f"{AUTH_URL}:{operation}?key={api_key}"

    try:
        response = requests.post(
            url,
            json={
                "email": email.strip(),
                "password": password,
                "returnSecureToken": True,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise FirebaseAuthError(
            "Não foi possível conectar ao Firebase Authentication. Tente novamente."
        ) from exc

    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as exc:
        raise FirebaseAuthError(
            "O Firebase Authentication retornou uma resposta inválida."
        ) from exc

    if not response.ok:
        error = payload.get("error", {})
        code = str(error.get("message", ""))
        raise FirebaseAuthError(_auth_error_message(code.split(":")[0]))

    try:
        return {
            "uid": payload["localId"],
            "email": payload.get("email", email.strip()),
        }
    except KeyError as exc:
        raise FirebaseAuthError(
            "A resposta do Firebase Authentication está incompleta."
        ) from exc


def amount_to_cents(amount: float) -> int:
    try:
        value = Decimal(str(amount)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Informe um valor válido.") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError("O valor deve ser maior que zero.")
    return int(value * 100)


def format_brl(amount_cents: int) -> str:
    amount = Decimal(amount_cents) / 100
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace(
        "X", "."
    )
    return f"R$ {formatted}"


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    return date.today()


def _transaction_data(
    *,
    owner_uid: str,
    description: str,
    transaction_type: str,
    amount: float,
    transaction_date: date,
) -> dict[str, Any]:
    if transaction_type not in {"income", "expense"}:
        raise ValueError("Selecione receita ou despesa.")
    clean_description = description.strip()
    if not clean_description:
        raise ValueError("Informe uma descrição.")

    return {
        "owner_uid": owner_uid,
        "description": clean_description,
        "type": transaction_type,
        "amount_cents": amount_to_cents(amount),
        "date": datetime.combine(
            transaction_date, time.min, tzinfo=timezone.utc
        ),
        "updated_at": datetime.now(timezone.utc),
    }


def _load_transactions(db: firestore.Client, owner_uid: str) -> list[dict[str, Any]]:
    transactions = []
    for snapshot in (
        db.collection(TRANSACTIONS_COLLECTION)
        .where("owner_uid", "==", owner_uid)
        .stream()
    ):
        transaction = snapshot.to_dict()
        transaction["id"] = snapshot.id
        transactions.append(transaction)
    transactions.sort(
        key=lambda item: (item.get("date") or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    return transactions


def _set_page(page: str, transaction_id: str | None = None) -> None:
    st.session_state.page = page
    st.session_state.editing_transaction_id = transaction_id
    st.rerun()


def _apply_mobile_styles() -> None:
    st.html(
        """
        <style>
        .st-key-mobile_navigation {
            display: none;
        }

        @media (max-width: 640px) {
            [data-testid="stMainBlockContainer"] {
                padding: 1.25rem 1rem 2rem !important;
            }

            .stApp:has(.st-key-mobile_navigation) [data-testid="stMainBlockContainer"] {
                padding-bottom: 7rem !important;
            }

            [data-testid="stVerticalBlockBorderWrapper"] {
                border-radius: 18px !important;
            }

            .st-key-add_transaction {
                display: none !important;
            }

            .st-key-mobile_navigation {
                position: fixed;
                z-index: 999;
                right: 0;
                bottom: 0;
                left: 0;
                display: block;
                padding: 0.55rem 0.75rem calc(0.55rem + env(safe-area-inset-bottom));
                border-top: 1px solid rgba(128, 128, 128, 0.2);
                background: var(--background-color);
                box-shadow: 0 -6px 20px rgba(0, 0, 0, 0.08);
            }

            .st-key-mobile_navigation button {
                min-height: 3rem;
                padding: 0.5rem 0.2rem !important;
                border-radius: 12px !important;
                font-size: 0.78rem !important;
                box-shadow: none !important;
            }
        }
        </style>
        """
    )


def _render_mobile_navigation() -> None:
    with st.container(key="mobile_navigation"):
        home, add, palette, logout = st.columns(4, gap="small", wrap=False)
        if home.button(
            "Início",
            icon=":material/home:",
            width="stretch",
            key="mobile_nav_home",
        ):
            _set_page("dashboard")
        if add.button(
            "Novo",
            icon=":material/add:",
            type="primary",
            width="stretch",
            key="mobile_nav_add",
        ):
            _set_page("transaction_form")
        if palette.button(
            "Cores",
            icon=":material/palette:",
            width="stretch",
            key="mobile_nav_palette",
        ):
            _set_page("palette")
        if logout.button(
            "Sair",
            icon=":material/logout:",
            width="stretch",
            key="mobile_nav_logout",
        ):
            for key in ("uid", "email", "page", "editing_transaction_id"):
                st.session_state.pop(key, None)
            st.rerun()


@st.dialog("Excluir lançamento")
def _confirm_delete(
    db: firestore.Client, owner_uid: str, transaction_id: str, description: str
) -> None:
    st.write(f"Tem certeza que deseja excluir **{description}**?")
    cancel, confirm = st.columns(2)
    if cancel.button("Cancelar", width="stretch"):
        st.rerun()
    if confirm.button("Excluir", type="primary", width="stretch"):
        reference = db.collection(TRANSACTIONS_COLLECTION).document(transaction_id)
        try:
            snapshot = reference.get()
        except GoogleAPICallError:
            st.error("Não foi possível verificar o lançamento. Tente novamente.")
            return
        if not snapshot.exists or snapshot.to_dict().get("owner_uid") != owner_uid:
            st.error("Lançamento não encontrado ou sem permissão para excluí-lo.")
            return
        try:
            reference.delete()
        except GoogleAPICallError:
            st.error("Não foi possível excluir o lançamento. Tente novamente.")
            return
        st.rerun()


def _render_authentication() -> None:
    st.title("Meu financeiro", icon=":material/account_balance_wallet:")
    st.caption("Organize suas receitas, despesas e acompanhe seu saldo em tempo real.")
    with st.container(border=True):
        mode = st.segmented_control(
            "Acesso",
            options=["Entrar", "Criar conta"],
            default="Entrar",
            label_visibility="collapsed",
            key="auth_mode",
        )
        if mode is None:
            mode = "Entrar"

        with st.form("auth_form"):
            email = st.text_input("E-mail", autocomplete="email", placeholder="exemplo@email.com")
            password = st.text_input(
                "Senha",
                type="password",
                placeholder="Sua senha de acesso",
                autocomplete=(
                    "new-password" if mode == "Criar conta" else "current-password"
                ),
            )
            confirmation = None
            if mode == "Criar conta":
                confirmation = st.text_input(
                    "Confirme a senha",
                    type="password",
                    placeholder="Repita a senha para confirmação",
                    autocomplete="new-password",
                )
            submitted = st.form_submit_button(
                "Entrar" if mode == "Entrar" else "Criar conta",
                type="primary",
                width="stretch",
            )

        if not submitted and st.button(
            "Configurar paleta de cores",
            icon=":material/palette:",
            width="stretch",
            key="auth_palette_btn",
        ):
            _set_page("palette")
    if not submitted:
        return
    if not email.strip() or not password:
        st.error("Preencha o e-mail e a senha.")
        return
    if mode == "Criar conta":
        if password != confirmation:
            st.error("As senhas não conferem.")
            return
        if len(password) < 6:
            st.error("A senha precisa ter pelo menos 6 caracteres.")
            return

    try:
        user = authenticate(email, password, register=mode == "Criar conta")
    except (FirebaseConfigurationError, FirebaseAuthError) as exc:
        st.error(str(exc))
        return

    st.session_state.uid = user["uid"]
    st.session_state.email = user["email"]
    st.session_state.page = "dashboard"
    st.session_state.editing_transaction_id = None
    st.rerun()


def _render_transaction_form(db: firestore.Client, owner_uid: str) -> None:
    transaction_id = st.session_state.get("editing_transaction_id")
    existing: dict[str, Any] | None = None
    if transaction_id:
        try:
            snapshot = (
                db.collection(TRANSACTIONS_COLLECTION)
                .document(transaction_id)
                .get()
            )
        except GoogleAPICallError:
            st.error("Não foi possível carregar o lançamento para edição.")
            return
        if not snapshot.exists:
            st.error("Este lançamento não existe mais.")
            _set_page("dashboard")
        existing = snapshot.to_dict()
        if existing.get("owner_uid") != owner_uid:
            st.error("Você não tem permissão para editar este lançamento.")
            _set_page("dashboard")

    form_title = "Editar lançamento" if existing else "Novo lançamento"
    form_icon = "✏️" if existing else "➕"
    st.html(
        f"""
        <div style="margin-bottom: 1.25rem;">
            <div style="display: flex; align-items: center; gap: 0.65rem;">
                <span style="font-size: 1.6rem;">{form_icon}</span>
                <h1 style="margin: 0; font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em;">{form_title}</h1>
            </div>
            <p style="margin: 0.25rem 0 0 0; opacity: 0.7; font-size: 0.95rem;">
                Preencha os dados da movimentação financeira para manter seu controle atualizado.
            </p>
        </div>
        """
    )
    with st.form("transaction_form"):
        description = st.text_input(
            "Descrição",
            value=existing.get("description", "") if existing else "",
            placeholder="Ex: Salário, Aluguel, Supermercado...",
            max_chars=100,
        )
        transaction_type = st.segmented_control(
            "Tipo",
            options=["Receita", "Despesa"],
            default=(
                "Receita"
                if existing and existing.get("type") == "income"
                else "Despesa"
                if existing
                else "Receita"
            ),
        )
        amount = st.number_input(
            "Valor (R$)",
            min_value=0.01,
            value=(
                existing.get("amount_cents", 0) / 100
                if existing
                else 0.01
            ),
            step=0.01,
            format="%.2f",
        )
        transaction_date = st.date_input(
            "Data",
            value=_as_date(existing.get("date")) if existing else date.today(),
            format="DD/MM/YYYY",
        )
        save = st.form_submit_button(
            "Salvar lançamento", icon=":material/check:", type="primary", width="stretch"
        )

    cancel_col, _ = st.columns([2, 3])
    if cancel_col.button("← Cancelar e voltar", width="stretch"):
        _set_page("dashboard")

    if not save:
        return
    if transaction_type not in {"Receita", "Despesa"}:
        st.error("Selecione receita ou despesa.")
        return

    try:
        data = _transaction_data(
            owner_uid=owner_uid,
            description=description,
            transaction_type="income" if transaction_type == "Receita" else "expense",
            amount=amount,
            transaction_date=transaction_date,
        )
        collection = db.collection(TRANSACTIONS_COLLECTION)
        if existing:
            collection.document(transaction_id).update(data)
        else:
            data["created_at"] = datetime.now(timezone.utc)
            collection.add(data)
    except ValueError as exc:
        st.error(str(exc))
        return
    except GoogleAPICallError:
        st.error("Não foi possível salvar o lançamento. Tente novamente.")
        return

    st.session_state.page = "dashboard"
    st.session_state.editing_transaction_id = None
    st.rerun()


def _render_dashboard(db: firestore.Client, owner_uid: str) -> None:
    current_palette = st.session_state.get("current_palette") or load_palette()
    income_color = current_palette.get("incomeColor", DEFAULT_PALETTE["incomeColor"])
    expense_color = current_palette.get("expenseColor", DEFAULT_PALETTE["expenseColor"])

    with st.sidebar:
        st.html(
            """
            <div style="display: flex; align-items: center; gap: 0.65rem; padding: 0.25rem 0 0.85rem 0;">
                <div style="
                    width: 38px;
                    height: 38px;
                    border-radius: 12px;
                    background: linear-gradient(135deg, var(--primary-color) 0%, rgba(128,128,128,0.2) 100%);
                    color: #fff;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.25rem;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
                ">
                    💳
                </div>
                <div>
                    <div style="font-weight: 800; font-size: 1.1rem; line-height: 1.2;">Meu financeiro</div>
                    <div style="font-size: 0.75rem; opacity: 0.7;">Controle inteligente</div>
                </div>
            </div>
            """
        )
        st.caption("Conta conectada")
        user_email = st.session_state.get("email", "")
        st.html(
            f"""
            <div style="
                background-color: rgba(128, 128, 128, 0.08);
                padding: 0.5rem 0.75rem;
                border-radius: 10px;
                font-size: 0.85rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
                word-break: break-all;
                border: 1px solid rgba(128, 128, 128, 0.15);
                margin-bottom: 0.5rem;
            ">
                <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: var(--primary-color);"></span>
                <span style="font-weight: 500;">{user_email}</span>
            </div>
            """
        )
        st.divider()
        st.caption("Navegação")
        if st.button(
            "Lançamentos",
            icon=":material/dashboard:",
            width="stretch",
            type="primary",
            disabled=True,
            key="side_nav_dash",
        ):
            _set_page("dashboard")
        if st.button(
            "Paleta de cores",
            icon=":material/palette:",
            width="stretch",
            key="side_nav_palette",
        ):
            _set_page("palette")
        st.divider()
        if st.button("Sair da conta", icon=":material/logout:", width="stretch", key="side_nav_logout"):
            for key in ("uid", "email", "page", "editing_transaction_id"):
                st.session_state.pop(key, None)
            st.rerun()

    st.title("Meu financeiro", icon=":material/account_balance_wallet:")
    st.caption("Acompanhe suas entradas, saídas e o saldo da sua conta.")

    try:
        transactions = _load_transactions(db, owner_uid)
    except GoogleAPICallError:
        st.error("Não foi possível carregar seus lançamentos do Firestore.")
        return

    income_total = sum(
        item["amount_cents"]
        for item in transactions
        if item.get("type") == "income"
    )
    expense_total = sum(
        item["amount_cents"]
        for item in transactions
        if item.get("type") == "expense"
    )
    saldo_total = income_total - expense_total
    saldo_color = income_color if saldo_total >= 0 else expense_color
    saldo_tint = hex_to_rgba(saldo_color, 0.12)

    st.html(
        f"""
        <div style="
            margin: 1.25rem 0 1rem;
            padding: 1.35rem 1.4rem;
            border: 1px solid {hex_to_rgba(saldo_color, 0.24)};
            border-radius: 22px;
            background: linear-gradient(135deg, {saldo_tint}, rgba(128, 128, 128, 0.03));
        ">
            <div style="font-size: 0.82rem; font-weight: 700; opacity: 0.72;">
                SALDO ATUAL
            </div>
            <div style="
                margin-top: 0.35rem;
                color: {saldo_color};
                font-size: clamp(1.8rem, 7vw, 2.45rem);
                font-weight: 800;
                letter-spacing: -0.04em;
                line-height: 1.2;
                overflow-wrap: anywhere;
            ">
                {format_brl(saldo_total)}
            </div>
            <div style="margin-top: 0.4rem; font-size: 0.86rem; opacity: 0.72;">
                Resultado entre receitas e despesas
            </div>
        </div>
        """
    )

    income_column, expense_column = st.columns(2, border=True)
    income_column.metric("Receitas", format_brl(income_total))
    expense_column.metric("Despesas", format_brl(expense_total))

    st.subheader("Lançamentos", icon=":material/receipt_long:")
    st.caption(f"{len(transactions)} movimentações")

    if not transactions:
        with st.container(border=True):
            st.html(
                """
                <div style="text-align: center; padding: 2.5rem 1rem;">
                    <div style="font-size: 2.8rem; margin-bottom: 0.75rem;">📂</div>
                    <div style="font-size: 1.15rem; font-weight: 700; margin-bottom: 0.35rem;">Nenhum lançamento cadastrado</div>
                    <div style="font-size: 0.9rem; opacity: 0.75; max-width: 320px; margin: 0 auto;">
                        Comece clicando no botão <strong>+</strong> abaixo para registrar sua primeira receita ou despesa.
                    </div>
                </div>
                """
            )

    for transaction in transactions:
        with st.container(border=True, key=f"transaction-{transaction['id']}"):
            transaction_type = transaction.get("type")
            is_income = transaction_type == "income"
            label = "Receita" if is_income else "Despesa"
            amount_str = format_brl(transaction.get("amount_cents", 0))
            transaction_date = _as_date(transaction.get("date")).strftime("%d/%m/%Y")
            description = transaction.get("description", "Sem descrição")
            sign = "+" if is_income else "-"

            info_column, amount_column = st.columns([1.5, 1])
            with info_column:
                st.markdown(f"**{description}**")
                st.badge(
                    label,
                    icon=":material/trending_up:" if is_income else ":material/trending_down:",
                    color="green" if is_income else "red",
                )
                st.caption(transaction_date)
            with amount_column:
                st.markdown(
                    f"**{sign} {amount_str}**",
                    text_alignment="right",
                )

            edit_column, delete_column = st.columns(2)
            if edit_column.button(
                "Editar",
                key=f"edit_{transaction['id']}",
                icon=":material/edit:",
                help="Editar lançamento",
                width="stretch",
            ):
                _set_page("transaction_form", transaction["id"])

            if delete_column.button(
                "Excluir",
                key=f"delete_{transaction['id']}",
                icon=":material/delete:",
                help="Excluir lançamento",
                width="stretch",
            ):
                _confirm_delete(
                    db,
                    owner_uid,
                    transaction["id"],
                    description,
                )

    add_columns = st.columns([4, 1, 4])
    with add_columns[1]:
        with st.container(key="add_transaction"):
            if st.button(
                "Adicionar lançamento",
                key="add_transaction_button",
                icon=":material/add:",
                type="primary",
                help="Adicionar receita ou despesa",
                width="stretch",
            ):
                _set_page("transaction_form")
    _render_mobile_navigation()


def main() -> None:
    st.set_page_config(
        page_title="Meu financeiro",
        page_icon=":material/account_balance_wallet:",
        layout="centered",
    )
    if "current_palette" not in st.session_state:
        st.session_state.current_palette = load_palette()
    apply_palette_css(st.session_state.current_palette)
    _apply_mobile_styles()

    st.session_state.setdefault("page", "dashboard")
    st.session_state.setdefault("editing_transaction_id", None)

    if st.session_state.get("page") == "palette":
        def _on_palette_back() -> None:
            _set_page("dashboard")
        render_palette_screen(on_back=_on_palette_back)
        return

    if not st.session_state.get("uid"):
        _render_authentication()
        return

    try:
        db = get_firestore_client()
    except (
        FirebaseConfigurationError,
        FirebaseError,
        GoogleAPICallError,
        GoogleAuthError,
        OSError,
        ValueError,
    ):
        st.error(
            "Não foi possível conectar ao Firestore. Confira a credencial Admin "
            "e o banco de dados configurado."
        )
        return

    if st.session_state.get("page") == "transaction_form":
        _render_transaction_form(db, st.session_state.uid)
    else:
        _render_dashboard(db, st.session_state.uid)


if __name__ == "__main__":
    main()
