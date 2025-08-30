import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from utils.db import get_connection
import os

@st.cache_data
def list_schemas(_conn):
    result = _conn.execute(text("SELECT schema_name FROM information_schema.schemata"))
    return [row[0] for row in result]

@st.cache_data
def list_user_schemas(user_email: str):
    from utils.db import get_engine
    with get_engine().connect() as conn:
        query = text("""
            SELECT DISTINCT p.schema_name
            FROM auth.users u
            JOIN auth.user_groups ug ON u.id = ug.user_id
            JOIN auth.group_schema_permissions p ON ug.group_id = p.group_id
            WHERE u.email = :email
            ORDER BY p.schema_name;
        """)
        result = conn.execute(query, {"email": user_email})
        return [row[0] for row in result]

@st.cache_data
def list_tables(schema_name: str):
    from utils.db import get_engine
    with get_engine().connect() as conn:
        result = conn.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema
            """),
            {"schema": schema_name}
        )
        return {row[0]: f"{schema_name}.{row[0]}" for row in result}

@st.cache_data(ttl=3600)
def load_table(_conn, table_id):
    try:
        if _conn.in_transaction():
            try:
                _conn.rollback()
            except Exception as e:
                st.error(f"Chyba při rollbacku: {e}")
                return pd.DataFrame()

        result = _conn.execute(text(f"SELECT * FROM {table_id}"))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df  # ← musí být tady, ne mimo try

    except Exception as e:
        st.error(f"Došlo k chybě při práci s databází: {e}")
        return pd.DataFrame()

def load_table_filtered(conn, table_id, where=None):
    query = f"SELECT * FROM {table_id}"
    if where:
        query += f" WHERE {where}"
    result = conn.execute(text(query))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    return df

def replace_table(conn, table_id, df):
    schema_name, table_name = table_id.split('.', 1)

    # ✅ Pokud běží stará transakce, zahoď ji
    if conn.in_transaction():
        conn.rollback()

    try:
        with conn.begin():  # začni novou transakci
            conn.execute(text(f'DROP TABLE IF EXISTS {table_id} CASCADE'))

            # Vytvoření nové tabulky podle DataFrame
            create_sql = pd.io.sql.get_schema(df, table_name, con=conn, schema=schema_name)
            conn.execute(text(create_sql))

            # Naplnění tabulky
            df.to_sql(table_name, conn, schema=schema_name, if_exists='append', index=False, method='multi')

    except Exception as e:
        if conn.in_transaction():
            conn.rollback()
        raise

def display_data_editor(df_to_edit, editor_key):
    edited_df = st.data_editor(
        df_to_edit,
        num_rows="dynamic",
        width='stretch',
        key=editor_key
    )
    return edited_df

def clear_filter_callback():
    st.session_state.where_input = ""
    st.session_state.where_clause = ""
    st.session_state.filter_applied = False
    st.session_state.reload_data = True

def main_data_browser():
    st.set_page_config(layout="wide")
    st.title("📊 Data browser")

    conn = get_connection()

    if "message" in st.session_state:
        st.success(st.session_state.message)
        del st.session_state.message

    if "editor_key_counter" not in st.session_state:
        st.session_state.editor_key_counter = 0
    if "filter_applied" not in st.session_state:
        st.session_state.filter_applied = False
    if "where_clause" not in st.session_state:
        st.session_state.where_clause = ""

    # Načteme schémata specifická pro přihlášeného uživatele
    schemas = list_user_schemas(st.session_state.user_email)

    # Důležitá kontrola pro případ, že uživatel nemá přístup nikam
    if not schemas:
        st.warning("Nemáte přiřazeno oprávnění k žádnému schématu. Obraťte se na administrátora.")
        st.stop()

    selected_schema = st.selectbox(
        "📁 Vyber schéma",
        schemas,
        # 'public' už nemusí být vždy dostupné, tak index nastavíme na 0
        index=0,
        key="selected_schema"
    )

    tables_dict = list_tables(selected_schema)

    if not tables_dict:
        st.info("Zvolené schéma neobsahuje žádnou tabulku.")
        st.stop()

    selected_table_name = st.selectbox("📂 Vyber tabulku", options=list(tables_dict.keys()))
    selected_table_id = tables_dict[selected_table_name]

    if not selected_table_id:
        st.info("Nebyla vybrána žádná validní tabulka.")
        st.stop()

    col_expander, col2, col3, _, _ = st.columns([2.5, 1, 1, 0.5, 0.5])

    with col_expander:
        expander_label = "🔍 Filtrováno" if st.session_state.filter_applied else "🔍 Filtr"
        expander_style = (
            "background-color: rgba(255, 255, 0, 0.1); border-radius: 5px;"
            if st.session_state.filter_applied else ""
        )

        with st.expander(expander_label):
            where_clause = st.text_input(
                "Zadej WHERE podmínku (bez klíčového slova 'WHERE')",
                placeholder="např.: amount > 100 AND status = 'active'",
                key="where_input"
            )
            col_clear_btn, col_filter_btn = st.columns(2)
            with col_clear_btn:
                st.button("❌ Zrušit filtr", key="clear_filter_button", on_click=clear_filter_callback)
            with col_filter_btn:
                apply_filter = st.button("🔽 Filtrovat", key="filter_button")

    if "reload_data" not in st.session_state:
        st.session_state.reload_data = True

    df = None

    if apply_filter and where_clause:
        st.session_state.where_clause = where_clause
        st.session_state.filter_applied = True
        st.session_state.reload_data = True
        st.rerun()

    elif st.session_state.reload_data:
        if st.session_state.filter_applied and st.session_state.where_clause:
            df = load_table_filtered(conn, selected_table_id, st.session_state.where_clause)
        else:
            df = load_table(conn, selected_table_id)
        st.session_state.reload_data = False

    if df is None:
        df = load_table(conn, selected_table_id)

    editor_key = f"editor_{st.session_state.editor_key_counter}"
    edited_df = display_data_editor(df, editor_key)

    if col2.button("🔁 ROLLBACK", width='stretch'):
        load_table.clear()
        st.session_state.reload_data = True
        st.session_state.editor_key_counter += 1
        st.session_state.message = "Změny byly zahozeny (ROLLBACK) – data byla znovu načtena z databáze."
        st.rerun()

    if col3.button("💾 COMMIT", width='stretch'):
        # KROK 1: Zkontrolujeme oprávnění uživatele na základě nového modelu
        schema_name, _ = selected_table_id.split('.', 1)
        user_permissions = st.session_state.get('permissions', {})
        permission_for_schema = user_permissions.get(schema_name)

        # Oprávnění 'write' je vyžadováno pro změn
        if permission_for_schema != 'write':
            st.error(f"🚫 Nemáte oprávnění 'write' k zápisu do schématu '{schema_name}'.")
        else:
            # KROK 2: Pokud má uživatel oprávnění 'write', provedeme původní logiku
            try:
                # ... (zbytek logiky pro COMMIT zůstává stejný) ...
                replace_table(conn, selected_table_id, edited_df)
                load_table.clear()
                st.session_state.reload_data = True
                st.session_state.editor_key_counter += 1
                st.session_state.message = "Změny byly uloženy (COMMIT)."
                st.rerun()
            except Exception as e:
                st.error(f"Chyba při COMMITu: {e}")

    with st.expander("⬇️ Export do CSV"):
        csv = edited_df.to_csv(index=False).encode('utf-8')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{selected_table_name}_{timestamp}.csv"
        st.download_button(
            "📥 Stáhnout aktuální pohled jako CSV",
            csv,
            file_name=file_name,
            mime='text/csv'
        )

    with st.expander("⬆️ Import CSV – přepsání tabulky"):
        uploaded_file = st.file_uploader("Vyber CSV soubor", type="csv")
        if uploaded_file:
            try:
                imported_df = pd.read_csv(uploaded_file)
                st.dataframe(imported_df, width='stretch')
                if st.button("🚨 Nahradit celou tabulku importovanými daty"):
                    replace_table(conn, selected_table_id, imported_df)
                    load_table.clear()
                    st.session_state.reload_data = True
                    st.session_state.editor_key_counter += 1
                    st.session_state.message = "Tabulka byla nahrazena."
                    st.rerun()
            except Exception as e:
                st.error(f"Chyba při importu: {e}")

if __name__ == "__main__":
    main_data_browser()