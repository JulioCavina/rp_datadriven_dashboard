# utils/filters.py
import streamlit as st
import pandas as pd
import json 

def aplicar_filtros(df, cookies):
    """Aplica filtros interativos no corpo principal da página, com estado persistente."""

    # ==================== NORMALIZAÇÃO ====================
    df.columns = df.columns.str.strip().str.lower()

    if "mes" not in df.columns: 
        possiveis = ["mês", "month", "mês referência", "mes_ref", "data", "date"]
        for c in possiveis:
            if c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    df["mes"] = df[c].dt.month
                else:
                    df["mes"] = pd.to_numeric(df[c], errors="coerce")
                break
        else:
            df["mes"] = 1

    if "ano" not in df.columns:
        possiveis_ano = ["ano_ref", "ano referência", "year", "data", "date"]
        for c in possiveis_ano:
            if c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    df["ano"] = df[c].dt.year
                else:
                    df["ano"] = pd.to_numeric(df[c], errors="coerce")
                break
        else:
            df["ano"] = 2024

    for col in ["emissora", "executivo", "cliente"]:
        if col not in df.columns:
            df[col] = ""

    df["ano"] = pd.to_numeric(df["ano"], errors="coerce").fillna(0).astype(int)
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce").fillna(0).astype(int)


    # ==================== DADOS BASE PARA FILTROS ====================
    anos_disponiveis = sorted(df["ano"].dropna().unique())
    emisoras = sorted(df["emissora"].dropna().unique())
    execs = sorted(df["executivo"].dropna().unique())
    clientes = sorted(df["cliente"].dropna().unique())
    
    mes_map = {
        1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
    }
    mes_map_inverso = {v: k for k, v in mes_map.items()}
    
    meses_disponiveis_num = sorted(df[df["mes"].between(1, 12)]["mes"].dropna().unique())
    meses_disponiveis_nomes = [mes_map.get(m, m) for m in meses_disponiveis_num]


    # ==================== LÓGICA DE PERSISTÊNCIA (SESSION STATE) ====================
    
    default_ini = 2024 if 2024 in anos_disponiveis else (anos_disponiveis[0] if anos_disponiveis else 2024)
    default_fim = 2025 if 2025 in anos_disponiveis else (anos_disponiveis[-1] if anos_disponiveis else 2025)
    
    if "filtro_ano_ini" not in st.session_state:
        st.session_state["filtro_ano_ini"] = default_ini
    if "filtro_ano_fim" not in st.session_state:
        st.session_state["filtro_ano_fim"] = default_fim

    if "filtro_emis" not in st.session_state:
        st.session_state["filtro_emis"] = emisoras

    if "filtro_execs" not in st.session_state:
        st.session_state["filtro_execs"] = execs

    if "filtro_clientes" not in st.session_state:
        st.session_state["filtro_clientes"] = []

    if "filtro_meses_lista" not in st.session_state:
        st.session_state["filtro_meses_lista"] = meses_disponiveis_nomes
    
    if "filtro_show_labels" not in st.session_state:
        st.session_state["filtro_show_labels"] = True 

    # --- DEFINIÇÃO DO CALLBACK ---
    def reset_filtros_callback():
        st.session_state["filtro_ano_ini"] = default_ini
        st.session_state["filtro_ano_fim"] = default_fim
        st.session_state["filtro_emis"] = emisoras
        st.session_state["filtro_execs"] = execs
        st.session_state["filtro_clientes"] = []
        st.session_state["filtro_meses_lista"] = meses_disponiveis_nomes
        st.session_state["filtro_show_labels"] = True
        
        if cookies.get("app_filters"):
            del cookies["app_filters"] 
            cookies.save()
        
    # ==================== WIDGETS DE FILTRO ====================
    with st.container():
        st.markdown("<h3 style='color:#002b5c;'>Filtros Globais</h3>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("<label style='font-size: 1rem; color: #003366; font-weight: 600; margin-bottom: -10px;'>Período (Ano):</label>", unsafe_allow_html=True)
            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
                st.selectbox("De:", anos_disponiveis, key="filtro_ano_ini")
            with sub_col2:
                st.selectbox("Até:", anos_disponiveis, key="filtro_ano_fim")
        
        with col2:
            st.multiselect("Emissora(s):", emisoras, key="filtro_emis")

        with col3:
            st.multiselect("Executivo(s):", execs, key="filtro_execs")

        col4, col5, col6 = st.columns(3)
        
        with col4:
            st.multiselect("Mês(es):", meses_disponiveis_nomes, key="filtro_meses_lista")
        
        with col5:
            st.multiselect("Cliente(s):", clientes, key="filtro_clientes")
        
        with col6:
            sub_col6_A, sub_col6_B = st.columns(2)
            
            with sub_col6_A:
                st.markdown("<label style='font-size: 1rem; color: #003366; font-weight: 600; margin-bottom: -10px;'>Rótulos de Dados</label>", unsafe_allow_html=True)
                st.toggle("Rótulos de Dados", key="filtro_show_labels", help="Exibir/Ocultar rótulos", label_visibility="collapsed")
            
            with sub_col6_B:
                st.markdown("<label style='font-size: 1rem; color: #003366; font-weight: 600; margin-bottom: -10px;'>Ações</label>", unsafe_allow_html=True)
                st.button("Limpar Filtros", type="secondary", width='stretch', on_click=reset_filtros_callback)


    # ==================== APLICA FILTROS ====================
    ano_ini_sel = st.session_state["filtro_ano_ini"]
    ano_fim_sel = st.session_state["filtro_ano_fim"]
    
    ano_1 = min(ano_ini_sel, ano_fim_sel)
    ano_2 = max(ano_ini_sel, ano_fim_sel)
    anos_sel = list(range(ano_1, ano_2 + 1)) 
    
    emis_sel = st.session_state["filtro_emis"]
    exec_sel = st.session_state["filtro_execs"]
    cli_sel = st.session_state["filtro_clientes"]
    
    meses_sel_nomes = st.session_state["filtro_meses_lista"]
    meses_sel_num = [mes_map_inverso.get(m, -1) for m in meses_sel_nomes]
    
    mes_ini = min(meses_sel_num) if meses_sel_num else 1
    mes_fim = max(meses_sel_num) if meses_sel_num else 12
    
    show_labels = st.session_state["filtro_show_labels"]
    
    
    df_filtrado = df[
        (df["ano"].between(ano_1, ano_2)) &
        (df["emissora"].isin(emis_sel)) &
        (df["executivo"].isin(exec_sel)) &
        (df["mes"].isin(meses_sel_num))
    ]

    if cli_sel:
        df_filtrado = df_filtrado[df_filtrado["cliente"].isin(cli_sel)]

    st.divider()
    
    # Salva os filtros no Cookie
    try:
        current_filters = {
            "filtro_ano_ini": int(st.session_state["filtro_ano_ini"]),
            "filtro_ano_fim": int(st.session_state["filtro_ano_fim"]),
            "filtro_emis": st.session_state["filtro_emis"],
            "filtro_execs": st.session_state["filtro_execs"],
            "filtro_clientes": st.session_state["filtro_clientes"],
            "filtro_meses_lista": st.session_state["filtro_meses_lista"],
            "filtro_show_labels": st.session_state["filtro_show_labels"], 
        }
        cookies["app_filters"] = json.dumps(current_filters)
        cookies.save()
    except Exception:
        # CORREÇÃO: Ignora erro de chave duplicada do componente de cookies
        pass

    return df_filtrado, anos_sel, emis_sel, exec_sel, cli_sel, mes_ini, mes_fim, show_labels