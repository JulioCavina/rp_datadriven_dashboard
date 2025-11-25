# pages/perdas_ganhos.py

import streamlit as st
from utils.format import brl
import pandas as pd
import numpy as np
from utils.export import create_zip_package 

def color_delta(val):
    """Colore valores positivos de verde e negativos de vermelho."""
    if pd.isna(val) or val == "" or val == "-": return ""
    try:
        if isinstance(val, (int, float)):
            v = float(val)
        else:
            v = float(str(val).replace("%", "").replace("+", "").replace(",", "."))
            
        if v > 0: return "color: #16a34a; font-weight: 600;" 
        if v < 0: return "color: #dc2626; font-weight: 600;" 
    except (ValueError, TypeError): return ""
    return ""

def format_currency(val):
    """Formata moeda de forma abreviada ou completa dependendo do tamanho."""
    if pd.isna(val): return "R$ 0,00"
    val_abs = abs(val)
    sign = "-" if val < 0 else ""
    if val_abs >= 1_000_000:
        return f"{sign}R$ {val_abs/1_000_000:,.1f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")
    return brl(val)

def format_int(val):
    """Formata inteiros com separador de milhar."""
    if pd.isna(val) or val == 0: return "-"
    return f"{int(val):,}".replace(",", ".")

def render(df, mes_ini, mes_fim, show_labels, ultima_atualizacao=None):
    # Inicialização de DFs para exportação
    df_perdas_raw = pd.DataFrame()
    df_ganhos_raw = pd.DataFrame()
    var_cli_raw = pd.DataFrame()
    var_emis_raw = pd.DataFrame()
    
    # Normalização básica
    df = df.rename(columns={c: c.lower() for c in df.columns})
    
    # Garante coluna insercoes
    if "insercoes" not in df.columns:
        df["insercoes"] = 0.0
    
    # ==================== LÓGICA DE ANOS (AUTOMÁTICA) ====================
    anos = sorted(df["ano"].dropna().unique())
    
    if not anos:
        st.info("Sem anos válidos na base.")
        return
    
    if len(anos) >= 2:
        ano_base, ano_comp = anos[-2], anos[-1]
    else:
        ano_base = ano_comp = anos[-1]

    # ==================== TÍTULO CENTRALIZADO ====================
    st.markdown(
        f"<h2 style='text-align: center; color: #003366;'>Perdas & Ganhos ({ano_base} vs {ano_comp})</h2>", 
        unsafe_allow_html=True
    )
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    if "cliente" not in df.columns or "faturamento" not in df.columns:
        st.error("Colunas obrigatórias 'Cliente' e/ou 'Faturamento' ausentes.")
        return

    # Filtra período (Meses) e separa as bases
    base_periodo = df[df["mes"].between(mes_ini, mes_fim)]
    baseA = base_periodo[base_periodo["ano"] == ano_base]
    baseB = base_periodo[base_periodo["ano"] == ano_comp]

    # ==================== CÁLCULOS DE CHURN E NOVOS NEGÓCIOS ====================
    cliA = set(baseA["cliente"].unique())
    cliB = set(baseB["cliente"].unique())
    
    # Listas de Clientes
    lista_perdas = sorted(list(cliA - cliB))
    lista_ganhos = sorted(list(cliB - cliA))

    # Totais Gerais (Financeiro)
    totalA = baseA["faturamento"].sum()
    totalB = baseB["faturamento"].sum()
    
    # Totais Gerais (Volume)
    totalInsA = baseA["insercoes"].sum()
    totalInsB = baseB["insercoes"].sum()
    
    # Valores Perdidos/Ganhos (Financeiro)
    val_perdas = baseA[baseA["cliente"].isin(lista_perdas)]["faturamento"].sum()
    val_ganhos = baseB[baseB["cliente"].isin(lista_ganhos)]["faturamento"].sum()

    # Valores Perdidos/Ganhos (Inserções)
    ins_perdas = baseA[baseA["cliente"].isin(lista_perdas)]["insercoes"].sum()
    ins_ganhos = baseB[baseB["cliente"].isin(lista_ganhos)]["insercoes"].sum()

    pct_perdas = (val_perdas / totalA * 100) if totalA > 0 else 0
    pct_ganhos = (val_ganhos / totalB * 100) if totalB > 0 else 0

    # ==================== DETALHAMENTO (PERDAS E GANHOS) ====================
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clientes Perdidos", len(lista_perdas))
    c2.metric(f"Valor Perdido ({ano_base})", brl(val_perdas))
    c3.metric(f"Inserções Perdidas", format_int(ins_perdas))
    c4.metric(f"% Impacto ({ano_base})", f"-{pct_perdas:.2f}%") 
    
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Clientes Novos", len(lista_ganhos))
    c6.metric(f"Valor Ganho ({ano_comp})", brl(val_ganhos))
    c7.metric(f"Inserções Ganhas", format_int(ins_ganhos))
    c8.metric(f"% Impacto ({ano_comp})", f"+{pct_ganhos:.2f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    # TABELAS LADO A LADO
    colA, colB = st.columns(2)
    
    # Tabela Perdas
    with colA:
        st.subheader(f"1. Clientes Perdidos (Saíram de {ano_base})")
        if lista_perdas:
            # Agrupa soma de Faturamento e Inserções
            df_perdas_raw = (baseA[baseA["cliente"].isin(lista_perdas)]
                             .groupby("cliente", as_index=False)
                             .agg(faturamento=("faturamento", "sum"), insercoes=("insercoes", "sum"))
                             .sort_values("faturamento", ascending=False)
                             .reset_index(drop=True))
            
            if not df_perdas_raw.empty:
                # Totalizador
                total_row = pd.DataFrame([{
                    "cliente": "Totalizador", 
                    "faturamento": df_perdas_raw["faturamento"].sum(),
                    "insercoes": df_perdas_raw["insercoes"].sum()
                }])
                df_perdas_raw = pd.concat([df_perdas_raw, total_row], ignore_index=True)

            df_perdas_raw.insert(0, "#", list(range(1, len(df_perdas_raw))) + ["Total"])
            
            t_display = df_perdas_raw.copy()
            t_display = t_display.rename(columns={
                "cliente": "Cliente", 
                "faturamento": "Faturamento", 
                "insercoes": "Inserções"
            })
            t_display['#'] = t_display['#'].astype(str)
            t_display["Faturamento"] = t_display["Faturamento"].apply(brl)
            t_display["Inserções"] = t_display["Inserções"].apply(format_int)
            
            st.dataframe(t_display, width="stretch", hide_index=True, column_config={"#": None})
        else: 
            st.success("Nenhum cliente perdido neste período!")

    # Tabela Ganhos
    with colB:
        st.subheader(f"2. Clientes Novos (Entraram em {ano_comp})")
        if lista_ganhos:
            # Agrupa soma de Faturamento e Inserções
            df_ganhos_raw = (baseB[baseB["cliente"].isin(lista_ganhos)]
                             .groupby("cliente", as_index=False)
                             .agg(faturamento=("faturamento", "sum"), insercoes=("insercoes", "sum"))
                             .sort_values("faturamento", ascending=False)
                             .reset_index(drop=True))
            
            if not df_ganhos_raw.empty:
                # Totalizador
                total_row = pd.DataFrame([{
                    "cliente": "Totalizador", 
                    "faturamento": df_ganhos_raw["faturamento"].sum(),
                    "insercoes": df_ganhos_raw["insercoes"].sum()
                }])
                df_ganhos_raw = pd.concat([df_ganhos_raw, total_row], ignore_index=True)

            df_ganhos_raw.insert(0, "#", list(range(1, len(df_ganhos_raw))) + ["Total"])
            
            t_display = df_ganhos_raw.copy()
            t_display = t_display.rename(columns={
                "cliente": "Cliente", 
                "faturamento": "Faturamento",
                "insercoes": "Inserções"
            })
            t_display['#'] = t_display['#'].astype(str)
            t_display["Faturamento"] = t_display["Faturamento"].apply(brl)
            t_display["Inserções"] = t_display["Inserções"].apply(format_int)
            
            st.dataframe(t_display, width="stretch", hide_index=True, column_config={"#": None})
        else: 
            st.info("Nenhum cliente novo neste período.")

    st.divider()

    # Função auxiliar para montar tabela de variação complexa
    def build_variation_table(groupby_col, label_col):
        # Pivot de Faturamento
        piv_fat = base_periodo.groupby([groupby_col, "ano"])["faturamento"].sum().unstack(fill_value=0)
        # Pivot de Inserções
        piv_ins = base_periodo.groupby([groupby_col, "ano"])["insercoes"].sum().unstack(fill_value=0)
        
        # Garante colunas
        for ano in [ano_base, ano_comp]:
            if ano not in piv_fat.columns: piv_fat[ano] = 0.0
            if ano not in piv_ins.columns: piv_ins[ano] = 0.0
            
        # Junta tudo
        df_var = pd.concat([piv_fat, piv_ins], axis=1)
        # Renomeia colunas para facilitar acesso: [FatA, FatB, InsA, InsB]
        df_var.columns = [f"Fat_{ano_base}", f"Fat_{ano_comp}", f"Ins_{ano_base}", f"Ins_{ano_comp}"]
        
        # Deltas
        df_var["Δ Fat"] = df_var[f"Fat_{ano_comp}"] - df_var[f"Fat_{ano_base}"]
        df_var["Δ%"] = np.where(df_var[f"Fat_{ano_base}"] > 0, (df_var["Δ Fat"] / df_var[f"Fat_{ano_base}"]) * 100, np.nan)
        df_var["Δ Ins"] = df_var[f"Ins_{ano_comp}"] - df_var[f"Ins_{ano_base}"]
        
        df_var = df_var.reset_index().rename(columns={groupby_col: label_col})
        df_var = df_var.sort_values("Δ Fat", ascending=True)
        
        return df_var

    # ==================== VARIAÇÕES (COMPARATIVO DE CARTEIRA) ====================
    st.subheader("3. Variações por Cliente (Faturamento e Inserções)")
    
    var_cli_raw = build_variation_table("cliente", "Cliente")

    if not var_cli_raw.empty:
        # Totalizador
        total_fat_a = var_cli_raw[f"Fat_{ano_base}"].sum()
        total_fat_b = var_cli_raw[f"Fat_{ano_comp}"].sum()
        total_ins_a = var_cli_raw[f"Ins_{ano_base}"].sum()
        total_ins_b = var_cli_raw[f"Ins_{ano_comp}"].sum()
        
        row_total = pd.DataFrame([{
            "Cliente": "Totalizador", 
            f"Fat_{ano_base}": total_fat_a, 
            f"Fat_{ano_comp}": total_fat_b, 
            "Δ Fat": total_fat_b - total_fat_a,
            "Δ%": (total_fat_b - total_fat_a) / total_fat_a * 100 if total_fat_a > 0 else np.nan,
            f"Ins_{ano_base}": total_ins_a,
            f"Ins_{ano_comp}": total_ins_b,
            "Δ Ins": total_ins_b - total_ins_a
        }])
        var_cli_raw = pd.concat([var_cli_raw, row_total], ignore_index=True)
    
    # Display Variação
    var_cli_disp = var_cli_raw.copy()
    
    # Renomeia colunas para o display final (Mais amigável)
    col_map = {
        f"Fat_{ano_base}": f"R$ {ano_base}",
        f"Fat_{ano_comp}": f"R$ {ano_comp}",
        f"Ins_{ano_base}": f"Ins. {ano_base}",
        f"Ins_{ano_comp}": f"Ins. {ano_comp}",
    }
    var_cli_disp = var_cli_disp.rename(columns=col_map)
    
    st.dataframe(
        var_cli_disp.style.map(color_delta, subset=["Δ Fat", "Δ%", "Δ Ins"])
        .format({
            f"R$ {ano_base}": brl, 
            f"R$ {ano_comp}": brl, 
            "Δ Fat": brl, 
            "Δ%": lambda x: "—" if pd.isna(x) else f"{x:+.2f}%",
            f"Ins. {ano_base}": format_int,
            f"Ins. {ano_comp}": format_int,
            "Δ Ins": format_int
        }, na_rep="—"), 
        width="stretch", 
        hide_index=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ==================== VARIAÇÕES POR EMISSORA ====================
    st.subheader("4. Variações por Emissora (Faturamento e Inserções)")
    
    var_emis_raw = build_variation_table("emissora", "Emissora")
    
    if not var_emis_raw.empty:
        total_fat_a = var_emis_raw[f"Fat_{ano_base}"].sum()
        total_fat_b = var_emis_raw[f"Fat_{ano_comp}"].sum()
        total_ins_a = var_emis_raw[f"Ins_{ano_base}"].sum()
        total_ins_b = var_emis_raw[f"Ins_{ano_comp}"].sum()
        
        row_total_e = pd.DataFrame([{
            "Emissora": "Totalizador", 
            f"Fat_{ano_base}": total_fat_a, 
            f"Fat_{ano_comp}": total_fat_b, 
            "Δ Fat": total_fat_b - total_fat_a,
            "Δ%": (total_fat_b - total_fat_a) / total_fat_a * 100 if total_fat_a > 0 else np.nan,
            f"Ins_{ano_base}": total_ins_a,
            f"Ins_{ano_comp}": total_ins_b,
            "Δ Ins": total_ins_b - total_ins_a
        }])
        var_emis_raw = pd.concat([var_emis_raw, row_total_e], ignore_index=True)
        
    var_emis_disp = var_emis_raw.copy().rename(columns=col_map)
    
    st.dataframe(
        var_emis_disp.style.map(color_delta, subset=["Δ Fat", "Δ%", "Δ Ins"])
        .format({
            f"R$ {ano_base}": brl, 
            f"R$ {ano_comp}": brl, 
            "Δ Fat": brl, 
            "Δ%": lambda x: "—" if pd.isna(x) else f"{x:+.2f}%",
            f"Ins. {ano_base}": format_int,
            f"Ins. {ano_comp}": format_int,
            "Δ Ins": format_int
        }, na_rep="—"), 
        width="stretch", 
        hide_index=True
    )
    
    st.divider()

    # ==================== EXPORTAÇÃO ====================
    def get_filter_string():
        f = st.session_state 
        return (f"Comparativo: {ano_base} vs {ano_comp} | Meses: {', '.join(f.get('filtro_meses_lista', ['Todos']))}")

    if st.button("📥 Exportar Dados da Página", type="secondary"):
        st.session_state.show_perdas_export = True
    
    if ultima_atualizacao:
        st.caption(f"📅 Última atualização da base de dados: {ultima_atualizacao}")

    if st.session_state.get("show_perdas_export", False):
        @st.dialog("Opções de Exportação - Perdas & Ganhos")
        def export_dialog():
            # Prepara DFs para exportação (Renomeando colunas técnicas para nomes bonitos)
            df_p_exp = df_perdas_raw.rename(columns={"cliente": "Cliente", "faturamento": "Faturamento", "insercoes": "Inserções"}) if not df_perdas_raw.empty else None
            df_g_exp = df_ganhos_raw.rename(columns={"cliente": "Cliente", "faturamento": "Faturamento", "insercoes": "Inserções"}) if not df_ganhos_raw.empty else None
            
            # As tabelas de variação já foram renomeadas dentro da função build_variation_table
            df_vc_exp = var_cli_raw if not var_cli_raw.empty else None
            df_ve_exp = var_emis_raw if not var_emis_raw.empty else None

            table_options = {
                "1. Clientes Perdidos": {'df': df_p_exp}, 
                "2. Clientes Ganhos": {'df': df_g_exp}, 
                "3. Variações (Cliente)": {'df': df_vc_exp}, 
                "4. Variações (Emissora)": {'df': df_ve_exp}
            }
            available_options = [name for name, data in table_options.items() if data.get('df') is not None and not data['df'].empty]
            
            if not available_options:
                st.warning("Nenhuma tabela com dados foi gerada.")
                if st.button("Fechar", type="secondary"):
                    st.session_state.show_perdas_export = False
                    st.rerun()
                return
            st.write("Selecione os itens para exportar:")
            selected_names = st.multiselect("Itens", options=available_options, default=available_options)
            tables_to_export = {name: table_options[name] for name in selected_names}
            
            if not tables_to_export:
                st.error("Selecione pelo menos um item.")
                return

            try:
                filtro_str = get_filter_string()
                zip_data = create_zip_package(tables_to_export, filtro_str)
                st.download_button("Clique para baixar", data=zip_data, file_name=f"Perdas_Ganhos_{ano_base}_{ano_comp}.zip", mime="application/zip", on_click=lambda: st.session_state.update(show_perdas_export=False), type="secondary")
            except Exception as e:
                st.error(f"Erro ao gerar ZIP: {e}")

            if st.button("Cancelar", key="cancel_export", type="secondary"):
                st.session_state.show_perdas_export = False
                st.rerun()
        export_dialog()