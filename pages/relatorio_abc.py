# pages/relatorio_abc.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from utils.format import brl, PALETTE
from utils.export import create_zip_package 

def format_int(val):
    """Formata inteiros com separador de milhar."""
    if pd.isna(val) or val == 0: return "-"
    return f"{int(val):,}".replace(",", ".")

def render(df, mes_ini, mes_fim, show_labels, ultima_atualizacao=None):
    # ==================== TÍTULO CENTRALIZADO ====================
    st.markdown("<h2 style='text-align: center; color: #003366;'>Relatório ABC (Pareto)</h2>", unsafe_allow_html=True)
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # Legenda explicativa com as novas cores
    st.markdown("""
    <div style='font-size: 0.9rem; color: #555; margin-bottom: 10px; text-align: center;'>
    <b>Classificação:</b> 
    <span style='color:#FFD700; font-weight:bold; text-shadow: 1px 1px 1px #999;'>Classe A</span> (até 80%) • 
    <span style='color:#A9A9A9; font-weight:bold; text-shadow: 1px 1px 1px #ccc;'>Classe B</span> (próximos 15%) • 
    <span style='color:#A0522D; font-weight:bold;'>Classe C</span> (últimos 5%)
    </div>
    """, unsafe_allow_html=True)

    # Inicializa DF para exportação
    df_abc_export = pd.DataFrame()
    fig_pie = None 

    # Normalização
    df = df.rename(columns={c: c.lower() for c in df.columns})
    
    # Garante colunas
    if "cliente" not in df.columns or "faturamento" not in df.columns:
        st.error("Colunas obrigatórias ausentes.")
        return
    if "insercoes" not in df.columns:
        df["insercoes"] = 0.0

    # Filtros
    base_periodo = df[df["mes"].between(mes_ini, mes_fim)]
    
    if base_periodo.empty:
        st.info("Sem dados para o período selecionado.")
        return

    # ==================== SELETOR DE MÉTRICA ====================
    if "abc_metric" not in st.session_state:
        st.session_state.abc_metric = "Faturamento"
    
    criterio = st.session_state.abc_metric
    
    # Layout do seletor (Centralizado)
    _, col_sel, _ = st.columns([1, 2, 1])
    with col_sel:
        b1, b2 = st.columns(2)
        type_fat = "primary" if criterio == "Faturamento" else "secondary"
        type_ins = "primary" if criterio == "Inserções" else "secondary"
        
        if b1.button("Por Faturamento (R$)", type=type_fat, use_container_width=True):
            st.session_state.abc_metric = "Faturamento"
            st.rerun()
            
        if b2.button("Por Inserções (Qtd)", type=type_ins, use_container_width=True):
            st.session_state.abc_metric = "Inserções"
            st.rerun()

    st.divider()

    # ==================== CÁLCULO DO ABC ====================
    # 1. Agrupar por Cliente e Somar Métricas
    df_abc = base_periodo.groupby("cliente", as_index=False).agg(
        faturamento=("faturamento", "sum"),
        insercoes=("insercoes", "sum")
    )
    
    # 2. Definir coluna alvo para ordenação e corte
    target_col = "faturamento" if criterio == "Faturamento" else "insercoes"
    
    # 3. Ordenar
    df_abc = df_abc.sort_values(target_col, ascending=False).reset_index(drop=True)
    
    # 4. Calcular Share e Acumulado
    total_target = df_abc[target_col].sum()
    df_abc["share"] = (df_abc[target_col] / total_target) if total_target > 0 else 0
    df_abc["acumulado"] = df_abc["share"].cumsum()
    
    # 5. Definir Classes
    def definir_classe(acum):
        if acum <= 0.80: return "A"
        elif acum <= 0.95: return "B"
        return "C"
    
    df_abc["classe"] = df_abc["acumulado"].apply(definir_classe)
    
    # 6. Vitaminar com Custo Médio
    df_abc["custo_medio"] = np.where(
        df_abc["insercoes"] > 0, 
        df_abc["faturamento"] / df_abc["insercoes"], 
        np.nan
    )

    # ==================== KPIs DO TOPO ====================
    # Agrupa por classe para os cards
    resumo_classes = df_abc.groupby("classe").agg(
        Qtd_Clientes=("cliente", "count"),
        Total_Faturamento=("faturamento", "sum"),
        Total_Insercoes=("insercoes", "sum")
    ).reindex(["A", "B", "C"]).fillna(0)
    
    c1, c2, c3 = st.columns(3)
    
    # Define qual valor mostrar no card (R$ ou Qtd)
    def get_kpi_display(row):
        if criterio == "Faturamento":
            return brl(row["Total_Faturamento"])
        else:
            return f"{int(row['Total_Insercoes']):,}".replace(",", ".") + " ins."

    # Classe A
    qtd_a = int(resumo_classes.loc["A", "Qtd_Clientes"])
    val_a = get_kpi_display(resumo_classes.loc["A"])
    c1.metric("Classe A (Vitais)", f"{qtd_a} Clientes", val_a, border=True)
    
    # Classe B
    qtd_b = int(resumo_classes.loc["B", "Qtd_Clientes"])
    val_b = get_kpi_display(resumo_classes.loc["B"])
    c2.metric("Classe B (Intermediários)", f"{qtd_b} Clientes", val_b, border=True)
    
    # Classe C
    qtd_c = int(resumo_classes.loc["C", "Qtd_Clientes"])
    val_c = get_kpi_display(resumo_classes.loc["C"])
    c3.metric("Classe C (Cauda Longa)", f"{qtd_c} Clientes", val_c, border=True)

    st.divider()

    # ==================== GRÁFICO E TABELA ====================
    col_graf, col_tab = st.columns([1, 2])
    
    with col_graf:
        st.markdown("<p class='custom-chart-title'>1. Distribuição da Carteira (Clientes)</p>", unsafe_allow_html=True)
        
        # Cores Personalizadas (Ouro, Prata, Bronze Enferrujado)
        abc_colors = {
            'A': '#FFD700',  # Ouro Vivo
            'B': '#C0C0C0',  # Prata
            'C': '#A0522D'   # Bronze/Sienna (Enferrujado)
        }

        # Gráfico de Pizza
        fig_pie = px.pie(
            resumo_classes.reset_index(), 
            values='Qtd_Clientes', 
            names='classe', 
            color='classe',
            color_discrete_map=abc_colors,
            category_orders={"classe": ["A", "B", "C"]}, # Força ordem A -> B -> C
            hole=0.4
        )
        # Rótulos: Valor Bruto (Quantidade de Clientes)
        fig_pie.update_traces(textinfo='value')
        
        fig_pie.update_layout(height=350, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_pie, width="stretch")

    with col_tab:
        st.markdown("<p class='custom-chart-title'>2. Detalhamento dos Clientes</p>", unsafe_allow_html=True)
        
        # Prepara tabela para exibição
        df_display = df_abc.copy()
        df_display["share_fmt"] = (df_display["share"] * 100).apply(lambda x: f"{x:.2f}%")
        df_display["acum_fmt"] = (df_display["acumulado"] * 100).apply(lambda x: f"{x:.2f}%")
        
        # Formatação dos valores
        df_display["faturamento_fmt"] = df_display["faturamento"].apply(brl)
        df_display["insercoes_fmt"] = df_display["insercoes"].apply(format_int)
        
        # Custo Médio (ainda numérico para formatação via column_config se quisesse, mas vamos de string formatada)
        df_display["custo_fmt"] = df_display["custo_medio"].apply(lambda x: brl(x) if pd.notna(x) else "-")
        
        # Seleção e Renomeação
        cols_order = ["classe", "cliente", "faturamento_fmt", "insercoes_fmt", "custo_fmt", "share_fmt", "acum_fmt"]
        df_display = df_display[cols_order]
        df_display.columns = ["Classe", "Cliente", "Faturamento", "Inserções", "Custo Médio", "Share %", "% Acumulado"]
        
        # Index virando Ranking
        df_display.index = range(1, len(df_display) + 1)
        df_display.index.name = "Rank"
        
        # Configuração da Coluna "Custo Médio" (CMU)
        st.dataframe(
            df_display, 
            height=350, 
            width="stretch",
            column_config={
                "Custo Médio": st.column_config.Column(
                    label="CMU ℹ️",
                    help="Custo Médio Unitário"
                )
            }
        )
        
        # Guarda para exportação
        df_abc_export = df_abc.copy()
        df_abc_export.columns = ["Cliente", "Faturamento", "Inserções", "Share", "Acumulado", "Classe", "Custo Médio"]

    # ==================== EXPORTAÇÃO ====================
    st.divider()
    def get_filter_string():
        f = st.session_state 
        ano_ini = f.get("filtro_ano_ini", "N/A")
        ano_fim = f.get("filtro_ano_fim", "N/A")
        emis = ", ".join(f.get("filtro_emis", ["Todas"]))
        return (f"Período: {ano_ini}-{ano_fim} | Emissoras: {emis} | Critério ABC: {criterio}")

    if st.button("📥 Exportar Dados da Página", type="secondary"):
        st.session_state.show_abc_export = True
    
    if ultima_atualizacao:
        st.caption(f"📅 Última atualização da base de dados: {ultima_atualizacao}")

    if st.session_state.get("show_abc_export", False):
        @st.dialog("Opções de Exportação - Curva ABC")
        def export_dialog():
            table_options = {
                "1. Distribuição da Carteira (Dados)": {'df': resumo_classes.reset_index()},
                "1. Distribuição da Carteira (Gráfico HTML)": {'fig': fig_pie},
                "2. Detalhamento dos Clientes (Dados)": {'df': df_abc_export}
            }
            
            available_options = [name for name, data in table_options.items() if (data.get('df') is not None and not data['df'].empty) or (data.get('fig') is not None)]
            
            if not available_options:
                st.warning("Sem dados para exportar.")
                if st.button("Fechar", type="secondary"):
                    st.session_state.show_abc_export = False
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
                st.download_button("Clique para baixar", data=zip_data, file_name=f"Dashboard_ABC_{criterio}.zip", mime="application/zip", on_click=lambda: st.session_state.update(show_abc_export=False), type="secondary")
            except Exception as e:
                st.error(f"Erro ao gerar ZIP: {e}")

            if st.button("Cancelar", key="cancel_export", type="secondary"):
                st.session_state.show_abc_export = False
                st.rerun()
        export_dialog()