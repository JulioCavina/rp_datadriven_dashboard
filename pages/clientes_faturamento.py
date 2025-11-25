# pages/clientes_faturamento.py

import streamlit as st
import numpy as np
import pandas as pd
from utils.format import brl, PALETTE
from utils.loaders import load_main_base
from utils.export import create_zip_package 

def color_delta(val):
    """
    Colore valores. Aceita tanto float quanto strings formatadas (ex: '+15.20%').
    """
    if pd.isna(val) or val == "" or val == "-": 
        return ""
    
    try:
        if isinstance(val, (int, float)):
            v = float(val)
        else:
            clean_val = str(val).replace("%", "").replace("+", "").replace(",", ".")
            v = float(clean_val)

        if v > 0: return "color: #16a34a; font-weight: 600;" 
        if v < 0: return "color: #dc2626; font-weight: 600;" 
    except (ValueError, TypeError): 
        return ""
    return ""

def format_percent_col(val):
    """Converte valor numérico para string formatada ou hífen se nulo."""
    if pd.isna(val): return "-"
    return f"{val:+.2f}%"

def format_int(val):
    """Formata inteiros com separador de milhar, retornando '-' se 0 ou nulo."""
    if pd.isna(val) or val == 0: return "-"
    return f"{int(val):,}".replace(",", ".")

def render(df, mes_ini, mes_fim, show_labels, ultima_atualizacao=None):
    # Título Centralizado
    st.markdown("<h2 style='text-align: center; color: #003366;'>Clientes & Faturamento</h2>", unsafe_allow_html=True)
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # Normalização
    df = df.rename(columns={c: c.lower() for c in df.columns})
    
    # Garante colunas essenciais
    if "faturamento" not in df.columns:
        st.error("Coluna 'Faturamento' ausente na base.")
        return
    if "insercoes" not in df.columns:
        df["insercoes"] = 0.0

    # Definição dos Anos
    anos = sorted(df["ano"].dropna().unique())
    if not anos:
        st.info("Sem anos válidos.")
        return
    if len(anos) >= 2:
        ano_base, ano_comp = anos[-2], anos[-1]
    else:
        ano_base = ano_comp = anos[-1]

    base_periodo = df[df["mes"].between(mes_ini, mes_fim)]

    # Helper para calcular métricas extras (Inserções e Custo Unitário) e mesclar
    def enrich_with_metrics(df_main, group_col):
        # Agrupa base_periodo para pegar totais
        agg = base_periodo.groupby(group_col).agg(
            Total_Fat=("faturamento", "sum"),
            Total_Ins=("insercoes", "sum")
        ).reset_index()
        
        # Cálculo do Custo Unitário (Evita divisão por zero)
        agg["Custo Unit."] = np.where(
            agg["Total_Ins"] > 0, 
            agg["Total_Fat"] / agg["Total_Ins"], 
            np.nan # Se não tem inserção, custo unitário não se aplica (ou poderia ser o valor cheio, mas visualmente '-' é melhor)
        )
        
        # Merge com a tabela principal (que já tem os anos e deltas)
        df_merged = pd.merge(df_main, agg[[group_col, "Total_Ins", "Custo Unit."]], on=group_col, how="left")
        
        # Preenche vazios
        df_merged["Total_Ins"] = df_merged["Total_Ins"].fillna(0)
        
        return df_merged

    # ==================== 1. CLIENTES POR EMISSORA ====================
    st.subheader("1. Número de Clientes por Emissora (Comparativo)")
    base_clientes_raw = (
        base_periodo.groupby(["emissora", "ano"])["cliente"]
        .nunique().unstack(fill_value=0).reset_index()
    )
    for ano in [ano_base, ano_comp]:
        if ano not in base_clientes_raw.columns: base_clientes_raw[ano] = 0

    base_clientes_raw["Δ"] = base_clientes_raw[ano_comp] - base_clientes_raw[ano_base]
    base_clientes_raw["Δ%"] = np.where(base_clientes_raw[ano_base] > 0, (base_clientes_raw["Δ"] / base_clientes_raw[ano_base]) * 100, np.nan)
    
    # Totalizador
    if not base_clientes_raw.empty:
        total_A = base_clientes_raw[ano_base].sum()
        total_B = base_clientes_raw[ano_comp].sum()
        total_delta = total_B - total_A
        total_pct = (total_delta / total_A * 100) if total_A > 0 else np.nan
        total_row = {"emissora": "Totalizador", ano_base: total_A, ano_comp: total_B, "Δ": total_delta, "Δ%": total_pct}
        base_clientes_raw = pd.concat([base_clientes_raw, pd.DataFrame([total_row])], ignore_index=True)

    base_clientes_raw.insert(0, "#", list(range(1, len(base_clientes_raw))) + ["Total"])
    
    # Display
    base_clientes_display = base_clientes_raw.copy()
    base_clientes_display = base_clientes_display.rename(columns={"emissora": "Emissora"})
    base_clientes_display.columns = base_clientes_display.columns.map(str)
    base_clientes_display['#'] = base_clientes_display['#'].astype(str)
    base_clientes_display["Δ%"] = base_clientes_display["Δ%"].apply(format_percent_col)

    st.dataframe(
        base_clientes_display.style.map(color_delta, subset=["Δ", "Δ%"]), 
        hide_index=True, width="stretch", column_config={"#": None}
    )
    st.divider()

    # ==================== 2. FATURAMENTO POR EMISSORA (COM INSERÇÕES) ====================
    st.subheader("2. Faturamento por Emissora (com Eficiência)")
    
    # Pivot de Faturamento
    base_emissora_raw = base_periodo.groupby(["emissora", "ano"])["faturamento"].sum().unstack(fill_value=0).reset_index()
    for ano in [ano_base, ano_comp]:
        if ano not in base_emissora_raw.columns: base_emissora_raw[ano] = 0.0

    base_emissora_raw["Δ"] = base_emissora_raw[ano_comp] - base_emissora_raw[ano_base]
    base_emissora_raw["Δ%"] = np.where(base_emissora_raw[ano_base] > 0, (base_emissora_raw["Δ"] / base_emissora_raw[ano_base]) * 100, np.nan)
    
    # Adiciona Inserções e Custo Unitário
    base_emissora_raw = enrich_with_metrics(base_emissora_raw, "emissora")

    # Totalizador
    if not base_emissora_raw.empty:
        total_A = base_emissora_raw[ano_base].sum()
        total_B = base_emissora_raw[ano_comp].sum()
        total_delta = total_B - total_A
        total_pct = (total_delta / total_A * 100) if total_A > 0 else np.nan
        
        total_ins = base_emissora_raw["Total_Ins"].sum()
        total_fat_periodo = base_periodo["faturamento"].sum()
        total_custo = total_fat_periodo / total_ins if total_ins > 0 else np.nan

        total_row = {
            "emissora": "Totalizador", 
            ano_base: total_A, 
            ano_comp: total_B, 
            "Δ": total_delta, 
            "Δ%": total_pct,
            "Total_Ins": total_ins,
            "Custo Unit.": total_custo
        }
        base_emissora_raw = pd.concat([base_emissora_raw, pd.DataFrame([total_row])], ignore_index=True)

    base_emissora_raw.insert(0, "#", list(range(1, len(base_emissora_raw))) + ["Total"])
    
    # Display
    base_emissora_display = base_emissora_raw.copy()
    base_emissora_display = base_emissora_display.rename(columns={
        "emissora": "Emissora",
        "Total_Ins": "Inserções (Total)",
        "Custo Unit.": "Custo Médio (R$)"
    })
    base_emissora_display.columns = base_emissora_display.columns.map(str)
    base_emissora_display['#'] = base_emissora_display['#'].astype(str)
    base_emissora_display["Δ%"] = base_emissora_display["Δ%"].apply(format_percent_col)
    
    # Formatação de colunas extras
    base_emissora_display["Inserções (Total)"] = base_emissora_display["Inserções (Total)"].apply(format_int)
    base_emissora_display["Custo Médio (R$)"] = base_emissora_display["Custo Médio (R$)"].apply(brl)

    st.dataframe(
        base_emissora_display.style.map(color_delta, subset=["Δ", "Δ%"])
        .format({str(ano_base): brl, str(ano_comp): brl, "Δ": brl}), 
        hide_index=True, width="stretch", column_config={"#": None}
    )
    st.divider()

    # ==================== 3. FATURAMENTO POR EXECUTIVO (COM INSERÇÕES) ====================
    st.subheader("3. Faturamento por Executivo (com Eficiência)")
    tx_raw = base_periodo.groupby(["executivo", "ano"])["faturamento"].sum().unstack(fill_value=0).reset_index()
    for ano in [ano_base, ano_comp]:
        if ano not in tx_raw.columns: tx_raw[ano] = 0.0

    tx_raw["Δ"] = tx_raw[ano_comp] - tx_raw[ano_base]
    tx_raw["Δ%"] = np.where(tx_raw[ano_base] > 0, (tx_raw["Δ"] / tx_raw[ano_base]) * 100, np.nan)
    
    # Adiciona Inserções
    tx_raw = enrich_with_metrics(tx_raw, "executivo")

    if not tx_raw.empty:
        total_A = tx_raw[ano_base].sum()
        total_B = tx_raw[ano_comp].sum()
        total_delta = total_B - total_A
        total_pct = (total_delta / total_A * 100) if total_A > 0 else np.nan
        total_ins = tx_raw["Total_Ins"].sum()
        total_custo = base_periodo["faturamento"].sum() / total_ins if total_ins > 0 else np.nan

        total_row = {
            "executivo": "Totalizador", 
            ano_base: total_A, 
            ano_comp: total_B, 
            "Δ": total_delta, 
            "Δ%": total_pct,
            "Total_Ins": total_ins,
            "Custo Unit.": total_custo
        }
        tx_raw = pd.concat([tx_raw, pd.DataFrame([total_row])], ignore_index=True)

    tx_raw.insert(0, "#", list(range(1, len(tx_raw))) + ["Total"])
    
    # Display
    tx_display = tx_raw.copy()
    tx_display = tx_display.rename(columns={
        "executivo": "Executivo",
        "Total_Ins": "Inserções",
        "Custo Unit.": "Custo Médio"
    })
    tx_display.columns = tx_display.columns.map(str)
    tx_display['#'] = tx_display['#'].astype(str)
    tx_display["Δ%"] = tx_display["Δ%"].apply(format_percent_col)
    tx_display["Inserções"] = tx_display["Inserções"].apply(format_int)
    tx_display["Custo Médio"] = tx_display["Custo Médio"].apply(brl)

    st.dataframe(
        tx_display.style.map(color_delta, subset=["Δ", "Δ%"])
        .format({
            str(ano_base): brl, 
            str(ano_comp): brl, 
            "Δ": brl
        }), 
        hide_index=True, width="stretch", column_config={"#": None}
    )
    st.divider()

    # ==================== 4. MÉDIAS (INVESTIMENTO E INSERÇÕES) ====================
    st.subheader("4. Médias por Cliente (Investimento e Inserções)")
    t16_raw = base_periodo.groupby("emissora").agg(
        Faturamento=("faturamento", "sum"), 
        Insercoes=("insercoes", "sum"),
        Clientes=("cliente", "nunique")
    ).reset_index()
    
    t16_raw["Média Invest./Cliente"] = np.where(t16_raw["Clientes"] == 0, np.nan, t16_raw["Faturamento"] / t16_raw["Clientes"])
    t16_raw["Média Inserções/Cliente"] = np.where(t16_raw["Clientes"] == 0, np.nan, t16_raw["Insercoes"] / t16_raw["Clientes"])
    
    if not t16_raw.empty:
        total_fat = t16_raw["Faturamento"].sum()
        total_ins = t16_raw["Insercoes"].sum()
        total_cli = base_periodo["cliente"].nunique() 
        
        med_fat = (total_fat / total_cli) if total_cli > 0 else np.nan
        med_ins = (total_ins / total_cli) if total_cli > 0 else np.nan
        
        total_row = {
            "emissora": "Totalizador", 
            "Faturamento": total_fat, 
            "Insercoes": total_ins,
            "Clientes": total_cli, 
            "Média Invest./Cliente": med_fat,
            "Média Inserções/Cliente": med_ins
        }
        t16_raw = pd.concat([t16_raw, pd.DataFrame([total_row])], ignore_index=True)

    t16_raw.insert(0, "#", list(range(1, len(t16_raw))) + ["Total"])
    
    t16_disp = t16_raw.copy()
    t16_disp = t16_disp.rename(columns={"emissora": "Emissora", "Insercoes": "Total Inserções"})
    
    # Formatações mistas
    t16_disp["Faturamento"] = t16_disp["Faturamento"].apply(brl)
    t16_disp["Total Inserções"] = t16_disp["Total Inserções"].apply(format_int)
    t16_disp["Média Invest./Cliente"] = t16_disp["Média Invest./Cliente"].apply(brl)
    t16_disp["Média Inserções/Cliente"] = t16_disp["Média Inserções/Cliente"].apply(lambda x: f"{x:,.1f}" if pd.notna(x) else "-")
    t16_disp['#'] = t16_disp['#'].astype(str)
    
    st.dataframe(t16_disp, width="stretch", hide_index=True, column_config={"#": None})
    st.divider()

    # ==================== 5. FATURAMENTO TOTAL ====================
    st.subheader("5. Faturamento por Emissora (Total)")
    # Reutiliza tabela 2, mas simplificada
    t15_raw = base_emissora_raw.copy()
    
    # Seleciona apenas colunas de totais
    cols_to_keep = ["emissora", "ano", "Δ", "Δ%", "Total_Ins", "Custo Unit."]
    # Mas aqui queremos só o total do periodo filtrado, vamos simplificar:
    t15_simple = base_periodo.groupby("emissora", as_index=False).agg(
        Faturamento=("faturamento", "sum"),
        Insercoes=("insercoes", "sum")
    ).sort_values("Faturamento", ascending=False)
    
    t15_simple["Custo Unitário"] = np.where(t15_simple["Insercoes"] > 0, t15_simple["Faturamento"] / t15_simple["Insercoes"], np.nan)

    if not t15_simple.empty:
        tot_fat = t15_simple["Faturamento"].sum()
        tot_ins = t15_simple["Insercoes"].sum()
        tot_custo = tot_fat / tot_ins if tot_ins > 0 else np.nan
        
        t15_simple = pd.concat([t15_simple, pd.DataFrame([{
            "emissora": "Totalizador", 
            "Faturamento": tot_fat, 
            "Insercoes": tot_ins,
            "Custo Unitário": tot_custo
        }])], ignore_index=True)
    
    t15_simple.insert(0, "#", list(range(1, len(t15_simple))) + ["Total"])
    
    t15_disp = t15_simple.copy().rename(columns={"emissora": "Emissora"})
    t15_disp["Faturamento"] = t15_disp["Faturamento"].apply(brl)
    t15_disp["Insercoes"] = t15_disp["Insercoes"].apply(format_int)
    t15_disp["Custo Unitário"] = t15_disp["Custo Unitário"].apply(brl)
    t15_disp['#'] = t15_disp['#'].astype(str)
    
    st.dataframe(t15_disp, width="stretch", hide_index=True, column_config={"#": None})
    st.divider()

    # ==================== 6. COMPARATIVO MÊS A MÊS ====================
    st.subheader("6. Comparativo mês a mês")
    mes_map = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}
    base_para_tabela = base_periodo.copy()
    base_para_tabela["mes_nome"] = base_para_tabela["mes"].map(mes_map)
    
    t14_agg = base_para_tabela.groupby(["ano", "mes", "mes_nome"])["faturamento"].sum().reset_index()
    t14_raw = t14_agg.pivot(index=["mes", "mes_nome"], columns="ano", values="faturamento").fillna(0.0)
    
    if not t14_raw.empty:
        t14_raw = t14_raw.sort_index(level="mes")
        t14_raw.index = t14_raw.index.get_level_values('mes_nome')
        t14_raw.index.name = "Mês"
        
        total_row = t14_raw.sum()
        total_row.name = "Totalizador"
        t14_raw = pd.concat([t14_raw, pd.DataFrame([total_row])])
        
        t14_disp = t14_raw.reset_index()
        t14_disp.columns = t14_disp.columns.map(str)
        
        format_dict = {col: brl for col in t14_disp.columns if col != "Mês"}
        st.dataframe(t14_disp.style.format(format_dict), width="stretch", hide_index=True)
    else:
        st.info("Sem dados suficientes para o comparativo mensal.")
    
    st.divider()

    # ==================== 7. RELAÇÃO DE CLIENTES (SHARE %) ====================
    st.subheader(f"7. Relação de Clientes ({ano_base} vs {ano_comp})")
    
    t17_raw = base_periodo.groupby(["cliente", "ano"])["faturamento"].sum().unstack(fill_value=0).reset_index()
    for ano in [ano_base, ano_comp]:
        if ano not in t17_raw.columns: t17_raw[ano] = 0.0
        
    t17_raw["Total"] = t17_raw[ano_base] + t17_raw[ano_comp]
    total_geral = t17_raw["Total"].sum()
    t17_raw["Share %"] = (t17_raw["Total"] / total_geral * 100) if total_geral > 0 else 0.0

    # Adiciona Inserções e Custo
    t17_raw = enrich_with_metrics(t17_raw, "cliente")

    t17_raw = t17_raw.sort_values("Total", ascending=False).reset_index(drop=True)
    
    if not t17_raw.empty:
        sum_A = t17_raw[ano_base].sum()
        sum_B = t17_raw[ano_comp].sum()
        sum_T = t17_raw["Total"].sum()
        sum_Ins = t17_raw["Total_Ins"].sum()
        avg_custo = sum_T / sum_Ins if sum_Ins > 0 else np.nan

        total_row_17 = {
            "cliente": "Totalizador", 
            ano_base: sum_A, 
            ano_comp: sum_B, 
            "Total": sum_T, 
            "Share %": 100.0,
            "Total_Ins": sum_Ins,
            "Custo Unit.": avg_custo
        }
        t17_raw = pd.concat([t17_raw, pd.DataFrame([total_row_17])], ignore_index=True)
        
    t17_disp = t17_raw.copy()
    t17_disp = t17_disp.rename(columns={
        "cliente": "Cliente",
        "Total_Ins": "Inserções (Qtd)",
        "Custo Unit.": "Custo Médio (R$)"
    })
    t17_disp.columns = t17_disp.columns.map(str) 
    
    # Formatação
    t17_disp["Inserções (Qtd)"] = t17_disp["Inserções (Qtd)"].apply(format_int)
    t17_disp["Custo Médio (R$)"] = t17_disp["Custo Médio (R$)"].apply(brl)

    st.dataframe(
        t17_disp.style.format({
            str(ano_base): brl, 
            str(ano_comp): brl, 
            "Total": brl,
            "Share %": "{:.2f}%"
        }), 
        width="stretch", 
        hide_index=True,
        height=450
    )

    st.divider()

    # ==================== EXPORTAÇÃO ====================
    def get_filter_string():
        f = st.session_state 
        ano_ini = f.get("filtro_ano_ini", "N/A")
        ano_fim = f.get("filtro_ano_fim", "N/A")
        emis = ", ".join(f.get("filtro_emis", ["Todas"]))
        execs = ", ".join(f.get("filtro_execs", ["Todos"]))
        meses = ", ".join(f.get("filtro_meses_lista", ["Todos"]))
        clientes = ", ".join(f.get("filtro_clientes", ["Todos"])) if f.get("filtro_clientes") else "Todos"
        return (f"Período (Ano): {ano_ini} a {ano_fim} | Meses: {meses} | Emissoras: {emis} | Executivos: {execs} | Clientes: {clientes}")

    if st.button("📥 Exportar Dados da Página", type="secondary"):
        st.session_state.show_clientes_export = True
    
    if ultima_atualizacao:
        st.caption(f"📅 Última atualização da base de dados: {ultima_atualizacao}")

    if st.session_state.get("show_clientes_export", False):
        @st.dialog("Opções de Exportação - Clientes & Faturamento")
        def export_dialog():
            t17_exp = t17_raw.rename(columns={"cliente": "Cliente"}) if not t17_raw.empty else None
            
            # Opções Atualizadas
            table_options = {
                "1. Clientes (Emissora)": {'df': base_clientes_raw},
                "2. Fat. + Inserções (Emissora)": {'df': base_emissora_raw},
                "3. Fat. + Inserções (Executivo)": {'df': tx_raw},
                "4. Médias Completas (Cliente)": {'df': t16_raw},
                "5. Fat. Total (Emissora)": {'df': t15_simple},
                "6. Comp. (Mês a Mês)": {'df': t14_raw.reset_index()},
                "7. Relação Clientes Detalhada": {'df': t17_exp},
            }
            available_options = [name for name, data in table_options.items() if data.get('df') is not None and not data['df'].empty]
            
            if not available_options:
                st.warning("Nenhuma tabela com dados foi gerada.")
                if st.button("Fechar", type="secondary"):
                    st.session_state.show_clientes_export = False
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
                st.download_button("Clique para baixar", data=zip_data, file_name="Dashboard_Clientes_Faturamento.zip", mime="application/zip", on_click=lambda: st.session_state.update(show_clientes_export=False), type="secondary")
            except Exception as e:
                st.error(f"Erro ao gerar ZIP: {e}")

            if st.button("Cancelar", key="cancel_export", type="secondary"):
                st.session_state.show_clientes_export = False
                st.rerun()
        export_dialog()