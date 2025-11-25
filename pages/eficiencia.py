# pages/eficiencia.py

import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from utils.format import brl, PALETTE
from utils.export import create_zip_package 

def render(df, mes_ini, mes_fim, show_labels, ultima_atualizacao=None):
    st.markdown("<h2 style='text-align: center; color: #003366;'>Eficiência & KPIs Avançados</h2>", unsafe_allow_html=True)
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # Normalização e Filtros
    df = df.rename(columns={c: c.lower() for c in df.columns})
    
    if "faturamento" not in df.columns or "cliente" not in df.columns:
        st.error("Colunas obrigatórias ausentes.")
        return
    
    if "insercoes" not in df.columns:
        df["insercoes"] = 0.0

    # Filtra período
    base_periodo = df[df["mes"].between(mes_ini, mes_fim)]
    
    # Filtra apenas quem tem faturamento > 0
    base_analise = base_periodo[base_periodo["faturamento"] > 0].copy()

    if base_analise.empty:
        st.info("Sem dados financeiros para o período.")
        return

    # ==================== CÁLCULOS DE KPI (MACRO) ====================
    total_fat = base_analise["faturamento"].sum()
    total_ins = base_analise["insercoes"].sum()
    
    # Custo Médio Geral (Yield Global)
    custo_medio_global = (total_fat / total_ins) if total_ins > 0 else 0
    
    # CPM Estimado (Proxy)
    cpm_proxy = (total_fat / (total_ins / 1000)) if total_ins > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Yield Médio (R$ / Inserção)", brl(custo_medio_global), help="Média geral de preço por inserção no período.")
    col2.metric("CPM (Custo p/ Mil Inserções)", brl(cpm_proxy))
    col3.metric("Volume Total Entregue", f"{int(total_ins):,}".replace(",", "."))

    st.divider()

    # ==================== 1. MATRIZ DE EFICIÊNCIA (GRÁFICO) ====================
    st.subheader("1. Matriz de Eficiência (Preço vs. Volume)")

    # Agrupa por Cliente e Emissora
    scatter_data = base_analise.groupby(["cliente", "emissora"], as_index=False).agg(
        Faturamento=("faturamento", "sum"),
        Insercoes=("insercoes", "sum")
    )
    
    # Calcula custo médio
    scatter_data["Custo_Medio"] = scatter_data["Faturamento"] / scatter_data["Insercoes"].replace(0, 1)
    
    # Filtra apenas quem tem inserção para o gráfico fazer sentido
    scatter_data = scatter_data[scatter_data["Insercoes"] > 0]

    # Definição de Cores Personalizadas
    color_map = {
        "Novabrasil": "#007dc3",  # Azul
        "Difusora": "#ef4444",    # Vermelho Leve
    }

    if not scatter_data.empty:
        fig_scatter = px.scatter(
            scatter_data,
            x="Insercoes",
            y="Custo_Medio",
            size="Faturamento",
            color="emissora",
            hover_name="cliente",
            log_x=False, 
            template="plotly_white",
            labels={
                "Insercoes": "Volume de Inserções (Qtd)",
                "Custo_Medio": "Preço Médio Pago (R$)",
                "emissora": "Emissora",
                "Faturamento": "Investimento Total"
            },
            color_discrete_map=color_map, 
            color_discrete_sequence=PALETTE 
        )
        
        # Linhas médias
        avg_x = scatter_data["Insercoes"].median()
        avg_y = scatter_data["Custo_Medio"].median()
        
        fig_scatter.add_hline(y=avg_y, line_dash="dot", annotation_text="Preço Médio", annotation_position="bottom right")
        fig_scatter.add_vline(x=avg_x, line_dash="dot", annotation_text="Vol. Médio", annotation_position="top right")

        fig_scatter.update_layout(height=500)
        st.plotly_chart(fig_scatter, width="stretch")
    else:
        st.warning("Dados insuficientes de inserções para gerar o gráfico.")

    # ==================== TABELA DE DADOS DO GRÁFICO ====================
    with st.expander("Ver dados detalhados da Matriz", expanded=True):
        if not scatter_data.empty:
            df_table = scatter_data.copy()
            
            # Formatação para exibição
            df_table["Faturamento_fmt"] = df_table["Faturamento"].apply(brl)
            df_table["Custo_Medio_fmt"] = df_table["Custo_Medio"].apply(brl)
            df_table["Insercoes_fmt"] = df_table["Insercoes"].apply(lambda x: f"{int(x):,}".replace(",", "."))
            
            # Seleção e Renomeação
            df_table = df_table[["cliente", "emissora", "Insercoes_fmt", "Faturamento_fmt", "Custo_Medio_fmt"]]
            df_table.columns = ["Cliente", "Emissora", "Inserções", "Faturamento Total", "Custo Unitário (R$)"]
            
            # CORREÇÃO: Ordenação Alfabética por Cliente
            df_table = df_table.sort_values("Cliente", ascending=True).reset_index(drop=True)
            
            # CORREÇÃO: hide_index=True para remover o ID
            st.dataframe(df_table, width="stretch", height=300, hide_index=True)
        else:
            st.info("Sem dados para exibir na tabela.")

    st.divider()

    # ==================== 2. RANKING DE EFICIÊNCIA POR EMISSORA ====================
    st.subheader("2. Resumo de Eficiência por Emissora")
    
    tb_eficiencia = base_analise.groupby("emissora", as_index=False).agg(
        Faturamento=("faturamento", "sum"),
        Insercoes=("insercoes", "sum"),
        Clientes=("cliente", "nunique")
    )
    
    tb_eficiencia["Yield (R$/Ins)"] = tb_eficiencia["Faturamento"] / tb_eficiencia["Insercoes"].replace(0, 1)
    tb_eficiencia["Ticket Médio (R$/Cli)"] = tb_eficiencia["Faturamento"] / tb_eficiencia["Clientes"]
    
    tb_eficiencia = tb_eficiencia.sort_values("Yield (R$/Ins)", ascending=False).reset_index(drop=True)
    
    tb_display = tb_eficiencia.copy()
    tb_display = tb_display.rename(columns={"emissora": "Emissora"})
    
    tb_display["Faturamento"] = tb_display["Faturamento"].apply(brl)
    tb_display["Insercoes"] = tb_display["Insercoes"].apply(lambda x: f"{int(x):,}".replace(",", "."))
    tb_display["Yield (R$/Ins)"] = tb_display["Yield (R$/Ins)"].apply(brl)
    tb_display["Ticket Médio (R$/Cli)"] = tb_display["Ticket Médio (R$/Cli)"].apply(brl)
    
    st.dataframe(tb_display, width="stretch", hide_index=True)

    # ==================== EXPORTAÇÃO ====================
    st.divider()
    def get_filter_string():
        f = st.session_state 
        return (f"Período: {f.get('filtro_ano_ini')}-{f.get('filtro_ano_fim')} | Meses: {', '.join(f.get('filtro_meses_lista', ['Todos']))}")

    if st.button("📥 Exportar Dados da Página", type="secondary"):
        st.session_state.show_efi_export = True
    
    if ultima_atualizacao:
        st.caption(f"📅 Última atualização da base de dados: {ultima_atualizacao}")

    if st.session_state.get("show_efi_export", False):
        @st.dialog("Opções de Exportação - Eficiência")
        def export_dialog():
            table_options = {
                "1. Matriz Eficiência (Dados Brutos)": {'df': scatter_data},
                "1. Matriz Eficiência (Gráfico HTML)": {'fig': fig_scatter if not scatter_data.empty else None},
                "2. Resumo por Emissora": {'df': tb_eficiencia}
            }
            
            available_options = [name for name, data in table_options.items() if (data.get('df') is not None and not data['df'].empty) or (data.get('fig') is not None)]
            
            if not available_options:
                st.warning("Sem dados para exportar.")
                if st.button("Fechar", type="secondary"):
                    st.session_state.show_efi_export = False
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
                st.download_button("Clique para baixar", data=zip_data, file_name="Dashboard_Eficiencia.zip", mime="application/zip", on_click=lambda: st.session_state.update(show_efi_export=False), type="secondary")
            except Exception as e:
                st.error(f"Erro ao gerar ZIP: {e}")

            if st.button("Cancelar", key="cancel_export", type="secondary"):
                st.session_state.show_efi_export = False
                st.rerun()
        export_dialog()