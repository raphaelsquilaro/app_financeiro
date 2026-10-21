from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / ".streamlit" / "config.toml"
PALETTE_FILE = APP_DIR / ".streamlit" / "palette.json"

DEFAULT_PALETTE: dict[str, str] = {
    "primaryColor": "#16856b",
    "backgroundColor": "#ffffff",
    "secondaryBackgroundColor": "#f3f7f5",
    "textColor": "#19352d",
    "incomeColor": "#16856b",
    "expenseColor": "#d32f2f",
    "font": "sans serif",
}

PALETTE_PRESETS: dict[str, dict[str, str]] = {
    "🌿 Verde Esmeralda (Padrão)": {
        "primaryColor": "#16856b",
        "backgroundColor": "#ffffff",
        "secondaryBackgroundColor": "#f3f7f5",
        "textColor": "#19352d",
        "incomeColor": "#16856b",
        "expenseColor": "#d32f2f",
        "font": "sans serif",
    },
    "🌊 Azul Oceano": {
        "primaryColor": "#0284c7",
        "backgroundColor": "#f8fafc",
        "secondaryBackgroundColor": "#f1f5f9",
        "textColor": "#0f172a",
        "incomeColor": "#059669",
        "expenseColor": "#dc2626",
        "font": "sans serif",
    },
    "🌌 Modo Noturno / Dark": {
        "primaryColor": "#818cf8",
        "backgroundColor": "#0f172a",
        "secondaryBackgroundColor": "#1e293b",
        "textColor": "#f8fafc",
        "incomeColor": "#34d399",
        "expenseColor": "#f87171",
        "font": "sans serif",
    },
    "🌇 Pôr do Sol": {
        "primaryColor": "#ea580c",
        "backgroundColor": "#fffbeb",
        "secondaryBackgroundColor": "#fef3c7",
        "textColor": "#451a03",
        "incomeColor": "#16a34a",
        "expenseColor": "#dc2626",
        "font": "sans serif",
    },
    "🌸 Framboesa & Rosa": {
        "primaryColor": "#db2777",
        "backgroundColor": "#fdf2f8",
        "secondaryBackgroundColor": "#fce7f3",
        "textColor": "#831843",
        "incomeColor": "#10b981",
        "expenseColor": "#e11d48",
        "font": "sans serif",
    },
    "🪙 Dourado & Preto": {
        "primaryColor": "#d97706",
        "backgroundColor": "#18181b",
        "secondaryBackgroundColor": "#27272a",
        "textColor": "#f4f4f5",
        "incomeColor": "#10b981",
        "expenseColor": "#ef4444",
        "font": "sans serif",
    },
    "🖤 Minimalista Grafite": {
        "primaryColor": "#475569",
        "backgroundColor": "#f1f5f9",
        "secondaryBackgroundColor": "#e2e8f0",
        "textColor": "#0f172a",
        "incomeColor": "#16a34a",
        "expenseColor": "#dc2626",
        "font": "sans serif",
    },
}


def load_palette() -> dict[str, str]:
    palette = dict(DEFAULT_PALETTE)

    # 1. Tenta carregar de palette.json se existir
    if PALETTE_FILE.is_file():
        try:
            stored = json.loads(PALETTE_FILE.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                palette.update({k: v for k, v in stored.items() if k in DEFAULT_PALETTE})
                return palette
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Tenta ler de config.toml na seção [theme]
    if CONFIG_PATH.is_file():
        try:
            toml_data = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            theme_section = toml_data.get("theme", {})
            if isinstance(theme_section, dict):
                palette.update({k: v for k, v in theme_section.items() if k in DEFAULT_PALETTE})
        except Exception:
            pass

    return palette


def _update_config_toml(palette: dict[str, str]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if CONFIG_PATH.is_file():
        try:
            lines = CONFIG_PATH.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []

    remaining_lines: list[str] = []
    in_theme = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_theme = (stripped.lower() == "[theme]")
            if in_theme:
                continue
        if not in_theme:
            remaining_lines.append(line)

    toml_theme_keys = ["primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor", "font"]
    theme_block = ["[theme]"]
    for key in toml_theme_keys:
        if key in palette:
            theme_block.append(f'{key} = "{palette[key]}"')

    other_content = "\n".join(remaining_lines).strip()
    new_toml = "\n".join(theme_block)
    if other_content:
        new_toml += "\n\n" + other_content
    new_toml += "\n"

    try:
        CONFIG_PATH.write_text(new_toml, encoding="utf-8")
    except OSError:
        pass


def save_palette(palette: dict[str, str], preset_name: str | None = None) -> None:
    data_to_store = dict(palette)
    if preset_name:
        data_to_store["preset"] = preset_name

    PALETTE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        PALETTE_FILE.write_text(
            json.dumps(data_to_store, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass

    _update_config_toml(palette)


def hex_to_rgba(hex_code: str, alpha: float) -> str:
    cleaned = hex_code.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(2 * c for c in cleaned)
    try:
        r, g, b = (int(cleaned[i:i+2], 16) for i in (0, 2, 4))
        return f"rgba({r}, {g}, {b}, {alpha})"
    except Exception:
        return f"rgba(128, 128, 128, {alpha})"


def build_theme_css(palette: dict[str, str]) -> str:
    primary = palette.get("primaryColor", DEFAULT_PALETTE["primaryColor"])
    bg = palette.get("backgroundColor", DEFAULT_PALETTE["backgroundColor"])
    sec_bg = palette.get("secondaryBackgroundColor", DEFAULT_PALETTE["secondaryBackgroundColor"])
    text = palette.get("textColor", DEFAULT_PALETTE["textColor"])
    income = palette.get("incomeColor", DEFAULT_PALETTE["incomeColor"])
    expense = palette.get("expenseColor", DEFAULT_PALETTE["expenseColor"])

    primary_shadow = hex_to_rgba(primary, 0.35)

    return f"""
    <style>
    :root {{
        --primary-color: {primary};
        --background-color: {bg};
        --secondary-background-color: {sec_bg};
        --text-color: {text};
        --finance-income: {income};
        --finance-expense: {expense};
    }}
    .stApp {{
        background-color: {bg};
        color: {text};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    [data-testid="stSidebar"] {{
        background-color: {sec_bg};
        color: {text};
        border-right: 1px solid rgba(128, 128, 128, 0.12);
    }}
    
    /* Modern card containers */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {sec_bg} !important;
        border-radius: 14px !important;
        border: 1px solid rgba(128, 128, 128, 0.16) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
        transition: transform 0.18s ease, box-shadow 0.18s ease !important;
    }}
    [data-testid="stVerticalBlockBorderWrapper"]:hover {{
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.07) !important;
    }}

    /* Primary buttons */
    button[kind="primary"], .stButton > button[kind="primary"] {{
        background-color: {primary} !important;
        border-color: {primary} !important;
        color: #ffffff !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.12) !important;
        transition: all 0.2s ease !important;
    }}
    button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover {{
        filter: brightness(1.08) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.18) !important;
    }}

    /* Secondary buttons */
    button[kind="secondary"], .stButton > button[kind="secondary"] {{
        border-radius: 10px !important;
        border: 1px solid rgba(128, 128, 128, 0.25) !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }}
    button[kind="secondary"]:hover, .stButton > button[kind="secondary"]:hover {{
        border-color: {primary} !important;
        color: {primary} !important;
    }}

    /* Inputs */
    div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="select"] {{
        border-radius: 10px !important;
    }}

    /* Round FAB + button */
    .st-key-add_transaction {{
        display: flex !important;
        justify-content: center !important;
        margin-top: 1.5rem !important;
        margin-bottom: 2rem !important;
    }}
    .st-key-add_transaction button {{
        border-radius: 50% !important;
        height: 3.8rem !important;
        width: 3.8rem !important;
        min-width: 3.8rem !important;
        padding: 0 !important;
        background-color: {primary} !important;
        border-color: {primary} !important;
        color: #ffffff !important;
        box-shadow: 0 6px 18px {primary_shadow} !important;
        transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.2s ease !important;
    }}
    .st-key-add_transaction button:hover {{
        transform: scale(1.12) !important;
        box-shadow: 0 8px 24px {primary_shadow} !important;
    }}
    .st-key-add_transaction button p {{
        font-size: 0 !important;
    }}

    /* Segmented Control */
    div[data-testid="stSegmentedControl"] {{
        background-color: rgba(128, 128, 128, 0.08) !important;
        padding: 3px !important;
        border-radius: 12px !important;
    }}
    </style>
    """


def apply_palette_css(palette: dict[str, str]) -> None:
    st.html(build_theme_css(palette))


def _find_matching_preset(colors: dict[str, str]) -> str:
    for name, preset_values in PALETTE_PRESETS.items():
        if all(colors.get(k) == v for k, v in preset_values.items() if k in colors):
            return name
    return "✨ Personalizado"


def render_palette_preview(colors: dict[str, str]) -> None:
    primary = colors.get("primaryColor", DEFAULT_PALETTE["primaryColor"])
    bg = colors.get("backgroundColor", DEFAULT_PALETTE["backgroundColor"])
    sec_bg = colors.get("secondaryBackgroundColor", DEFAULT_PALETTE["secondaryBackgroundColor"])
    text = colors.get("textColor", DEFAULT_PALETTE["textColor"])
    income = colors.get("incomeColor", DEFAULT_PALETTE["incomeColor"])
    expense = colors.get("expenseColor", DEFAULT_PALETTE["expenseColor"])

    income_tint = hex_to_rgba(income, 0.12)
    expense_tint = hex_to_rgba(expense, 0.12)
    saldo_tint = hex_to_rgba(primary, 0.1)

    preview_html = f"""
    <div style="
        background-color: {bg};
        color: {text};
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 18px rgba(0,0,0,0.06);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(128,128,128,0.18); padding-bottom: 0.85rem; margin-bottom: 1.25rem;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.4rem;">💳</span>
                <span style="font-weight: 800; font-size: 1.2rem; color: {text};">Meu financeiro</span>
            </div>
            <span style="font-size: 0.75rem; font-weight: 600; padding: 0.25rem 0.65rem; border-radius: 20px; background-color: {sec_bg}; color: {text}; border: 1px solid rgba(128,128,128,0.25);">
                ● Simulação ao vivo
            </span>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.85rem; margin-bottom: 1.25rem;">
            <div style="background: linear-gradient(135deg, {income_tint} 0%, rgba(128,128,128,0.02) 100%); border-radius: 12px; padding: 0.85rem 1rem; border: 1px solid {hex_to_rgba(income, 0.25)};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
                    <span style="font-size: 0.75rem; font-weight: 600; opacity: 0.75; text-transform: uppercase;">Receitas</span>
                    <span style="color: {income}; font-weight: 700; font-size: 0.85rem;">↗</span>
                </div>
                <div style="font-size: 1.25rem; font-weight: 800; color: {income};">R$ 5.200,00</div>
            </div>
            <div style="background: linear-gradient(135deg, {expense_tint} 0%, rgba(128,128,128,0.02) 100%); border-radius: 12px; padding: 0.85rem 1rem; border: 1px solid {hex_to_rgba(expense, 0.25)};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
                    <span style="font-size: 0.75rem; font-weight: 600; opacity: 0.75; text-transform: uppercase;">Despesas</span>
                    <span style="color: {expense}; font-weight: 700; font-size: 0.85rem;">↘</span>
                </div>
                <div style="font-size: 1.25rem; font-weight: 800; color: {expense};">R$ 1.850,00</div>
            </div>
            <div style="background: linear-gradient(135deg, {saldo_tint} 0%, rgba(128,128,128,0.02) 100%); border-radius: 12px; padding: 0.85rem 1rem; border: 1px solid rgba(128,128,128,0.25);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
                    <span style="font-size: 0.75rem; font-weight: 600; opacity: 0.75; text-transform: uppercase;">Saldo</span>
                    <span style="font-weight: 700; font-size: 0.85rem;">⚖️</span>
                </div>
                <div style="font-size: 1.25rem; font-weight: 800; color: {text};">R$ 3.350,00</div>
            </div>
        </div>

        <div style="margin-bottom: 1.25rem;">
            <div style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.8; margin-bottom: 0.6rem; color: {text};">Lançamentos recentes</div>
            
            <div style="background-color: {sec_bg}; border-radius: 10px; padding: 0.75rem 1rem; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center; border: 1px solid rgba(128,128,128,0.15);">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <div style="width: 32px; height: 32px; border-radius: 50%; background: {income_tint}; color: {income}; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.95rem;">↗</div>
                    <div>
                        <div style="font-weight: 700; font-size: 0.95rem; color: {text};">Salário mensal</div>
                        <div style="font-size: 0.75rem; opacity: 0.7; color: {text};">Receita · 15/10/2026</div>
                    </div>
                </div>
                <div style="color: {income}; font-weight: 800; font-size: 1.05rem;">+ R$ 5.200,00</div>
            </div>

            <div style="background-color: {sec_bg}; border-radius: 10px; padding: 0.75rem 1rem; display: flex; justify-content: space-between; align-items: center; border: 1px solid rgba(128,128,128,0.15);">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <div style="width: 32px; height: 32px; border-radius: 50%; background: {expense_tint}; color: {expense}; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.95rem;">↘</div>
                    <div>
                        <div style="font-weight: 700; font-size: 0.95rem; color: {text};">Supermercado & Feira</div>
                        <div style="font-size: 0.75rem; opacity: 0.7; color: {text};">Despesa · 14/10/2026</div>
                    </div>
                </div>
                <div style="color: {expense}; font-weight: 800; font-size: 1.05rem;">- R$ 850,00</div>
            </div>
        </div>

        <div style="display: flex; gap: 0.75rem; align-items: center; border-top: 1px solid rgba(128,128,128,0.18); padding-top: 0.85rem;">
            <div style="background-color: {primary}; color: #ffffff; padding: 0.5rem 1.25rem; border-radius: 8px; font-weight: 600; font-size: 0.85rem; box-shadow: 0 2px 6px rgba(0,0,0,0.12);">
                Botão Primário
            </div>
            <div style="background-color: {sec_bg}; color: {text}; border: 1px solid rgba(128,128,128,0.3); padding: 0.5rem 1.25rem; border-radius: 8px; font-size: 0.85rem; font-weight: 500;">
                Botão Secundário
            </div>
            <div style="width: 34px; height: 34px; border-radius: 50%; background-color: {primary}; color: #ffffff; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; font-weight: 700; box-shadow: 0 2px 6px rgba(0,0,0,0.15); margin-left: auto;">
                +
            </div>
        </div>
    </div>
    """
    st.html(preview_html)

    # Amostras de cores (Swatches)
    swatches_html = f"""
    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; margin-bottom: 1rem;">
        <div style="background-color: {sec_bg}; border: 1px solid rgba(128,128,128,0.2); border-radius: 8px; padding: 0.4rem 0.65rem; display: flex; align-items: center; gap: 0.45rem; font-size: 0.8rem;">
            <span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; background-color: {primary};"></span>
            <span>Primária: <code>{primary}</code></span>
        </div>
        <div style="background-color: {sec_bg}; border: 1px solid rgba(128,128,128,0.2); border-radius: 8px; padding: 0.4rem 0.65rem; display: flex; align-items: center; gap: 0.45rem; font-size: 0.8rem;">
            <span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; background-color: {bg}; border: 1px solid #aaa;"></span>
            <span>Fundo: <code>{bg}</code></span>
        </div>
        <div style="background-color: {sec_bg}; border: 1px solid rgba(128,128,128,0.2); border-radius: 8px; padding: 0.4rem 0.65rem; display: flex; align-items: center; gap: 0.45rem; font-size: 0.8rem;">
            <span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; background-color: {sec_bg}; border: 1px solid #aaa;"></span>
            <span>Secundário: <code>{sec_bg}</code></span>
        </div>
        <div style="background-color: {sec_bg}; border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 0.4rem 0.65rem; display: flex; align-items: center; gap: 0.45rem; font-size: 0.8rem;">
            <span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; background-color: {text};"></span>
            <span>Texto: <code>{text}</code></span>
        </div>
        <div style="background-color: {sec_bg}; border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 0.4rem 0.65rem; display: flex; align-items: center; gap: 0.45rem; font-size: 0.8rem;">
            <span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; background-color: {income};"></span>
            <span>Receita: <code>{income}</code></span>
        </div>
        <div style="background-color: {sec_bg}; border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 0.4rem 0.65rem; display: flex; align-items: center; gap: 0.45rem; font-size: 0.8rem;">
            <span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; background-color: {expense};"></span>
            <span>Despesa: <code>{expense}</code></span>
        </div>
    </div>
    """
    st.html(swatches_html)


def render_palette_screen(on_back: Callable[[], None] | None = None) -> None:
    current = st.session_state.get("current_palette") or load_palette()

    header_col, back_col = st.columns([5, 1])
    with header_col:
        st.title("🎨 Paleta de cores")
        st.caption("Personalize as cores da interface. Escolha um tema pronto ou defina cada cor individualmente.")
    with back_col:
        if st.button("Voltar", icon=":material/arrow_back:", width="stretch", key="palette_top_back"):
            if on_back:
                on_back()
            else:
                st.session_state.page = "dashboard"
                st.rerun()

    # Inicializa variáveis na session_state para os color pickers
    for key in ("primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor", "incomeColor", "expenseColor"):
        state_key = f"palette_{key}"
        if state_key not in st.session_state:
            st.session_state[state_key] = current.get(key, DEFAULT_PALETTE[key])

    current_colors = {
        key: st.session_state[f"palette_{key}"]
        for key in ("primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor", "incomeColor", "expenseColor")
    }

    # Seleção de Preset
    preset_options = list(PALETTE_PRESETS.keys()) + ["✨ Personalizado"]
    current_matched = _find_matching_preset(current_colors)
    default_index = preset_options.index(current_matched) if current_matched in preset_options else len(preset_options) - 1

    st.subheader("Temas prontos")

    def _on_preset_selected() -> None:
        chosen = st.session_state.preset_select_widget
        if chosen in PALETTE_PRESETS:
            for k, val in PALETTE_PRESETS[chosen].items():
                if f"palette_{k}" in st.session_state:
                    st.session_state[f"palette_{k}"] = val

    st.selectbox(
        "Selecione um tema pré-definido:",
        options=preset_options,
        index=default_index,
        key="preset_select_widget",
        on_change=_on_preset_selected,
    )

    chosen_preset_name = st.session_state.get("preset_select_widget")
    chosen_theme = PALETTE_PRESETS.get(chosen_preset_name, current_colors)
    p_col = chosen_theme.get("primaryColor", "#16856b")
    bg_col = chosen_theme.get("backgroundColor", "#ffffff")
    sec_col = chosen_theme.get("secondaryBackgroundColor", "#f3f7f5")
    txt_col = chosen_theme.get("textColor", "#19352d")
    inc_col = chosen_theme.get("incomeColor", "#16856b")
    exp_col = chosen_theme.get("expenseColor", "#d32f2f")

    st.html(
        f"""
        <div style="
            display: flex;
            height: 10px;
            border-radius: 6px;
            overflow: hidden;
            margin: 0.25rem 0 1rem 0;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            border: 1px solid rgba(128,128,128,0.2);
        ">
            <div style="flex: 2; background-color: {p_col};" title="Primária: {p_col}"></div>
            <div style="flex: 2; background-color: {bg_col}; border-left: 1px solid rgba(0,0,0,0.1);" title="Fundo: {bg_col}"></div>
            <div style="flex: 2; background-color: {sec_col}; border-left: 1px solid rgba(0,0,0,0.1);" title="Secundário: {sec_col}"></div>
            <div style="flex: 2; background-color: {txt_col};" title="Texto: {txt_col}"></div>
            <div style="flex: 2; background-color: {inc_col};" title="Receita: {inc_col}"></div>
            <div style="flex: 2; background-color: {exp_col};" title="Despesa: {exp_col}"></div>
        </div>
        """
    )

    # Seletores de cores
    st.subheader("Personalizar cores")
    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown("🎨 **Interface e Fundo**")
            st.color_picker(
                "Cor primária (Destaques e botões)",
                key="palette_primaryColor",
                help="Usada no botão de adicionar (+), botões de ação e itens destacados.",
            )
            st.color_picker(
                "Fundo principal",
                key="palette_backgroundColor",
                help="Cor de fundo geral do aplicativo.",
            )
            st.color_picker(
                "Fundo secundário (Cards e menu)",
                key="palette_secondaryBackgroundColor",
                help="Cor dos cartões de receitas/despesas e da barra lateral.",
            )

    with col2:
        with st.container(border=True):
            st.markdown("📈 **Tipografia e Finanças**")
            st.color_picker(
                "Cor do texto",
                key="palette_textColor",
                help="Cor dos textos e títulos principais da tela.",
            )
            st.color_picker(
                "Cor de receitas",
                key="palette_incomeColor",
                help="Cor dos valores de receitas e entradas financeiras.",
            )
            st.color_picker(
                "Cor de despesas",
                key="palette_expenseColor",
                help="Cor dos valores de despesas e saídas financeiras.",
            )

    # Cores atuais selecionadas após atualização dos widgets
    active_colors = {
        key: st.session_state[f"palette_{key}"]
        for key in ("primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor", "incomeColor", "expenseColor")
    }
    active_colors["font"] = "sans serif"

    # Callbacks para ações dos botões (executados antes da renderização dos widgets no rerun)
    def _save_callback() -> None:
        colors = {
            k: st.session_state[f"palette_{k}"]
            for k in ("primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor", "incomeColor", "expenseColor")
        }
        colors["font"] = "sans serif"
        save_palette(colors, preset_name=st.session_state.get("preset_select_widget"))
        st.session_state.current_palette = dict(colors)
        st.session_state["palette_status_msg"] = ("success", "Paleta salva e aplicada com sucesso!")

    def _reset_callback() -> None:
        for k, val in DEFAULT_PALETTE.items():
            state_k = f"palette_{k}"
            if state_k in st.session_state:
                st.session_state[state_k] = val
        st.session_state["preset_select_widget"] = "🌿 Verde Esmeralda (Padrão)"
        save_palette(DEFAULT_PALETTE, preset_name="🌿 Verde Esmeralda (Padrão)")
        st.session_state.current_palette = dict(DEFAULT_PALETTE)
        st.session_state["palette_status_msg"] = ("info", "Paleta padrão restaurada!")

    def _cancel_callback() -> None:
        for k in ("primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor", "incomeColor", "expenseColor"):
            st.session_state[f"palette_{k}"] = current.get(k, DEFAULT_PALETTE[k])
        if on_back:
            on_back()
        else:
            st.session_state.page = "dashboard"

    if status := st.session_state.pop("palette_status_msg", None):
        level, msg = status
        if level == "success":
            st.success(msg)
        else:
            st.info(msg)

    st.subheader("Pré-visualização em tempo real")
    render_palette_preview(active_colors)

    st.divider()

    # Botões de ação
    save_col, reset_col, cancel_col = st.columns([2, 2, 1])

    with save_col:
        st.button(
            "Salvar paleta",
            type="primary",
            icon=":material/check:",
            width="stretch",
            key="save_palette_btn",
            on_click=_save_callback,
        )

    with reset_col:
        st.button(
            "Restaurar padrão",
            icon=":material/restart_alt:",
            width="stretch",
            key="reset_palette_btn",
            on_click=_reset_callback,
        )

    with cancel_col:
        st.button(
            "Voltar",
            width="stretch",
            key="cancel_palette_btn",
            on_click=_cancel_callback,
        )
