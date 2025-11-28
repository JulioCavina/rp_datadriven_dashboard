# pages/visao_geral.py

import streamlit as st
import plotly.express as px
from utils.format import brl, PALETTE
import pandas as pd
import plotly.graph_objects as go 
from plotly.subplots import make_subplots
import numpy as np
from utils.export import create_zip_package 

# ==================== MAPA DE CORES ====================
COLOR_MAP = {
    "Novabrasil": "#6fa8dc",   # Azul suave
    "Difusora": "#9f86c0",     # Roxo/Lilás
    "Thathi Tv": "#93c47d",    # Verde suave
    "Th+ Prime": "#76a5af",    # Azul acinzentado
    # Fallback para variações de escrita
    "novabrasil": "#6fa8dc",
    "difusora": "#9f86c0",
    "thathi tv": "#93c47d",
    "th+ prime": "#76a5af"
}

# ==================== ESTILO CSS (CENTRALIZAÇÃO E ALINHAMENTO) ====================
ST_METRIC_CENTER = """
<style>
/* Container principal do Metric: Flexbox vertical centralizado */
[data-testid="stMetric"] {
    display: flex;
    flex-direction: column;
    align-items: center; /* Centraliza horizontalmente o bloco */
    justify-content: center; /* Centraliza verticalmente se houver altura fixa */
    text-align: center;
    width: 100%;
    margin: auto;
}

/* Rótulo (Título do Card) */
[data-testid="stMetricLabel"] {
    justify-content: center;
    width: 100%;
    margin-bottom: 0px !important; /* Aproxima do valor */
}

/* Valor (Número Grande) */
[data-testid="stMetricValue"] {
    justify-content: center;
    width: 100%;
}

/* Delta (Variação ou Texto abaixo) */
[data-testid="stMetricDelta"] {
    justify-content: center;
    width: 100%;
    margin-top: 0px !important; /* Aproxima do valor */
}
</style>
"""

def format_pt_br_abrev(val):
    if pd.isna(val): return "R$ 0"
    sign = "-" if val < 0 else ""
    val_abs = abs(val)
    if val_abs == 0: return "R$ 0"
    if val_abs >= 1_000_000: return f"{sign}R$ {val_abs/1_000_000:,.1f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")
    if val_abs >= 1_000: return f"{sign}R$ {val_abs/1_000:,.0f} mil".replace(",", "X").replace(".", ",").replace("X", ".")
    return brl(val)

def get_pretty_ticks(max_val, num_ticks=5):
    if max_val <= 0: return [0], ["R$ 0"], 100 
    ideal_interval = max_val / num_ticks
    magnitude = 10**np.floor(np.log10(ideal_interval)) if ideal_interval > 0 else 1
    residual = ideal_interval / magnitude
    if residual < 1.5: nice_interval = 1 * magnitude
    elif residual < 3: nice_interval = 2 * magnitude
    elif residual < 7: nice_interval = 5 * magnitude
    else: nice_interval = 10 * magnitude
    max_y_rounded = np.ceil(max_val / nice_interval) * nice_interval
    tick_values = np.arange(0, max_y_rounded + nice_interval, nice_interval)
    tick_texts = [format_pt_br_abrev(v) for v in tick_values]
    y_axis_cap = max_y_rounded * 1.05
    return tick_values, tick_texts, y_axis_cap

def get_top_client_info(df_base):
    """Retorna nome completo, valor e nome abreviado do maior cliente."""
    if df_base.empty:
        return "—", 0.0, "—"
    
    top_series = df_base.groupby("cliente")["faturamento"].sum().sort_values(ascending=False)
    if top_series.empty:
        return "—", 0.0, "—"
        
    nome_full = top_series.index[0]
    valor = top_series.iloc[0]
    
    # Trunca nome muito longo para exibição no card (visual), mas mantém full para tooltip
    nome_display = nome_full[:18] + "..." if len(nome_full) > 18 else nome_full
    return nome_full, valor, nome_display

def render(df, mes_ini, mes_fim, show_labels, ultima_atualizacao=None):
    # Aplica CSS para centralizar os cards e aproximar título/valor
    st.markdown(ST_METRIC_CENTER, unsafe_allow_html=True)

    # Título Centralizado
    st.markdown("<h2 style='text-align: center; color: #003366;'>Visão Geral</h2>", unsafe_allow_html=True)
    if ultima_atualizacao:
        st.caption(f"📅 Dados atualizados até: {ultima_atualizacao}")
    
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    evol_raw = pd.DataFrame()
    base_emis_raw = pd.DataFrame()
    base_exec_raw = pd.DataFrame()
    fig_evol = go.Figure()
    
    # Dicionário para armazenar figuras das roscas para exportação
    figs_share_dict = {}
    
    # ==================== PREPARAÇÃO DE DADOS ====================
    df = df.rename(columns={c: c.lower() for c in df.columns})

    if "emissora" in df.columns:
        df["emissora"] = df["emissora"].astype(str).str.strip().str.title()
        df["emissora"] = df["emissora"].replace({
            "Thathi": "Thathi Tv",
            "Th+": "Th+ Prime" 
        })

    if "insercoes" not in df.columns:
        df["insercoes"] = 0.0

    if "meslabel" not in df.columns:
        if "ano" in df.columns and "mes" in df.columns:
            df["meslabel"] = pd.to_datetime(dict(
                year=df["ano"].astype(int),
                month=df["mes"].astype(int),
                day=1
            )).dt.strftime("%b/%y")
        else:
            df["meslabel"] = ""

    anos = sorted(df["ano"].dropna().unique())
    if not anos:
        st.info("Sem anos válidos na base.")
        return
    if len(anos) >= 2:
        ano_base, ano_comp = anos[-2], anos[-1]
    else:
        ano_base = ano_comp = anos[-1]

    ano_base_str = str(ano_base)[-2:]
    ano_comp_str = str(ano_comp)[-2:]
    
    base_periodo = df[df["mes"].between(mes_ini, mes_fim)]
    baseA = base_periodo[base_periodo["ano"] == ano_base]
    baseB = base_periodo[base_periodo["ano"] == ano_comp]

    # ==================== KPI LINHA 1: TOTAIS (MACRO) ====================
    totalA = float(baseA["faturamento"].sum()) if not baseA.empty else 0.0
    totalB = float(baseB["faturamento"].sum()) if not baseB.empty else 0.0
    delta_abs = totalB - totalA
    delta_pct = (delta_abs / totalA * 100) if totalA > 0.0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Total {ano_base}", format_pt_br_abrev(totalA))
    c2.metric(f"Total {ano_comp}", format_pt_br_abrev(totalB))
    c3.metric(f"Δ Absoluto ({ano_comp_str}-{ano_base_str})", format_pt_br_abrev(delta_abs))
    c4.metric(f"Δ % ({ano_comp_str} vs {ano_base_str})", f"{delta_pct:.2f}%" if totalA > 0 else "—")

    # ==================== KPI LINHA 2: TICKET MÉDIO E MAIOR CLIENTE ====================
    # Ticket Médio Base A (Menor Ano)
    cliA = baseA["cliente"].nunique()
    tmA = totalA / cliA if cliA > 0 else 0.0
    
    # Ticket Médio Base B (Maior Ano)
    cliB = baseB["cliente"].nunique()
    tmB = totalB / cliB if cliB > 0 else 0.0

    # Maior Cliente Base A
    full_A, val_A, disp_A = get_top_client_info(baseA)
    # Maior Cliente Base B
    full_B, val_B, disp_B = get_top_client_info(baseB)

    st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True) 
    
    k1, k2, k3, k4 = st.columns(4)
    
    k1.metric(f"Ticket Médio ({ano_base})", format_pt_br_abrev(tmA))
    k2.metric(f"Ticket Médio ({ano_comp})", format_pt_br_abrev(tmB))
    
    k3.metric(
        label=f"Maior Cliente ({ano_base})", 
        value=format_pt_br_abrev(val_A),
        delta=disp_A, # Nome abreviado visível
        delta_color="off",
        help=f"Cliente: {full_A}" # Tooltip com nome completo
    )
    
    k4.metric(
        label=f"Maior Cliente ({ano_comp})", 
        value=format_pt_br_abrev(val_B),
        delta=disp_B, # Nome abreviado visível
        delta_color="off",
        help=f"Cliente: {full_B}" # Tooltip com nome completo
    )

    st.divider()

    # ==================== GRÁFICO 1: EVOLUÇÃO MENSAL ====================
    st.markdown("<p class='custom-chart-title'>1. Evolução Mensal de Faturamento e Inserções</p>", unsafe_allow_html=True)
    
    evol_raw = base_periodo.groupby(["ano", "meslabel", "mes"], as_index=False)[["faturamento", "insercoes"]].sum().sort_values(["ano", "mes"])
    
    if not evol_raw.empty:
        fig_evol = make_subplots(specs=[[{"secondary_y": True}]])

        # 1. Barras de Faturamento
        fig_evol.add_trace(
            go.Bar(
                x=evol_raw["meslabel"],
                y=evol_raw["faturamento"],
                name="Faturamento",
                marker_color=PALETTE[0],
                opacity=0.85
            ),
            secondary_y=False
        )

        # 2. Linha de Inserções
        fig_evol.add_trace(
            go.Scatter(
                x=evol_raw["meslabel"],
                y=evol_raw["insercoes"],
                name="Inserções",
                mode='lines+markers',
                line=dict(color='#dc2626', width=3),
                marker=dict(size=6)
            ),
            secondary_y=True
        )

        # Eixos
        max_y_fat = evol_raw['faturamento'].max()
        tick_vals, tick_txt, y_cap_fat = get_pretty_ticks(max_y_fat)
        
        fig_evol.update_yaxes(
            title_text="Faturamento (R$)", 
            tickvals=tick_vals, ticktext=tick_txt, 
            range=[0, y_cap_fat], secondary_y=False,
            showgrid=True, gridcolor='#f0f0f0'
        )
        
        max_y_ins = evol_raw['insercoes'].max()
        y_cap_ins = max_y_ins * 1.2 if max_y_ins > 0 else 10
        fig_evol.update_yaxes(
            title_text="Inserções (Qtd)", 
            range=[0, y_cap_ins], secondary_y=True,
            showgrid=False
        )

        fig_evol.update_layout(
            height=400, 
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"), 
            template="plotly_white",
            margin=dict(l=20, r=20, t=20, b=20)
        )
        
        if show_labels:
            for i, row in evol_raw.iterrows():
                fig_evol.add_annotation(
                    x=row["meslabel"], y=row["faturamento"], 
                    text=format_pt_br_abrev(row["faturamento"]),
                    showarrow=False, yshift=10, 
                    font=dict(size=10, color="black"),
                    bgcolor="rgba(255, 255, 255, 0.8)", borderpad=2,
                    secondary_y=False
                )
                if row["insercoes"] > 0:
                    fig_evol.add_annotation(
                        x=row["meslabel"], y=row["insercoes"], 
                        text=str(int(row["insercoes"])),
                        showarrow=False, yshift=15, 
                        font=dict(size=10, color="#dc2626", weight="bold"),
                        bgcolor="rgba(255, 255, 255, 0.7)", borderpad=2,
                        yref="y2", secondary_y=True
                    )

        st.plotly_chart(fig_evol, width="stretch") 
    else:
        st.info("Sem dados para o período selecionado.")

    st.divider()

    # ==================== GRÁFICO 2: FATURAMENTO POR EMISSORA ====================
    st.markdown("<p class='custom-chart-title'>2. Faturamento por Emissora (Ano a Ano)</p>", unsafe_allow_html=True)
    
    base_emis_raw = base_periodo.groupby(["emissora", "ano"], as_index=False)["faturamento"].sum()
    
    if not base_emis_raw.empty:
        # Ordenação e concatenação
        base_emis_raw = base_emis_raw.sort_values(["emissora", "ano"])
        base_emis_raw["label_x"] = base_emis_raw["emissora"] + " " + base_emis_raw["ano"].astype(str)
        
        fig_emis = px.bar(
            base_emis_raw, 
            x="label_x", 
            y="faturamento", 
            color="emissora", 
            color_discrete_map=COLOR_MAP,
            labels={"label_x": "Emissora / Ano", "faturamento": "Faturamento"}
        )
        
        max_y_emis = base_emis_raw['faturamento'].max()
        tick_vals_e, tick_txt_e, y_cap_e = get_pretty_ticks(max_y_emis)
        
        fig_emis.update_layout(
            height=400, xaxis_title=None, yaxis_title=None, 
            template="plotly_white", showlegend=True, legend_title="Emissora",
            bargap=0.2
        )
        fig_emis.update_traces(width=0.5) 

        fig_emis.update_yaxes(tickvals=tick_vals_e, ticktext=tick_txt_e, range=[0, y_cap_e])
        
        if show_labels:
            fig_emis.update_traces(text=base_emis_raw['faturamento'].apply(format_pt_br_abrev), textposition='outside')
            
        st.plotly_chart(fig_emis, width="stretch")
    else:
        st.info("Sem dados.")

    st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)

    # ==================== GRÁFICO 3: SHARE DE MERCADO ====================
    st.markdown("<p class='custom-chart-title'>3. Share Faturamento (%)</p>", unsafe_allow_html=True)
    
    anos_presentes = sorted(base_periodo["ano"].dropna().unique())
    if anos_presentes:
        cols_share = st.columns(len(anos_presentes))
        
        for idx, ano_share in enumerate(anos_presentes):
            df_share_ano = base_periodo[base_periodo["ano"] == ano_share].groupby("emissora", as_index=False)["faturamento"].sum()
            
            if not df_share_ano.empty:
                fig_share = px.pie(
                    df_share_ano, 
                    values="faturamento", 
                    names="emissora",
                    color="emissora",
                    color_discrete_map=COLOR_MAP,
                    hole=0.6 
                )
                fig_share.update_traces(textposition='inside', textinfo='percent+label')
                
                # Centralização do texto do ano
                fig_share.add_annotation(
                    text=f"<b>{ano_share}</b>", 
                    x=0.5, y=0.5, 
                    showarrow=False, 
                    font_size=20,
                    xanchor='center',
                    yanchor='middle'
                )

                fig_share.update_layout(
                    height=300, 
                    showlegend=False, 
                    margin=dict(l=10, r=10, t=10, b=10),
                )
                
                # NOME CORRIGIDO: 3. Share de Faturamento (Gráfico 202X)
                figs_share_dict[f"3. Share de Faturamento (Gráfico {ano_share})"] = fig_share
                
                with cols_share[idx]:
                    st.plotly_chart(fig_share, width="stretch")
            else:
                with cols_share[idx]:
                    st.info(f"Sem dados para {ano_share}")
    else:
        st.info("Sem dados para gerar gráfico de share.")

    st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)

    # ==================== GRÁFICO 4: FATURAMENTO POR EXECUTIVO ====================
    st.markdown("<p class='custom-chart-title'>4. Faturamento por Executivo (Ano a Ano)</p>", unsafe_allow_html=True)
    
    base_exec_raw = base_periodo.groupby(["executivo", "ano"], as_index=False)["faturamento"].sum()
    
    if not base_exec_raw.empty:
        rank_exec = base_exec_raw.groupby("executivo")["faturamento"].sum().sort_values(ascending=False).index.tolist()
        base_exec_raw["executivo"] = pd.Categorical(base_exec_raw["executivo"], categories=rank_exec, ordered=True)
        base_exec_raw = base_exec_raw.sort_values(["executivo", "ano"])
        base_exec_raw["label_x"] = base_exec_raw["executivo"].astype(str) + " " + base_exec_raw["ano"].astype(str)
        
        fig_exec = px.bar(
            base_exec_raw, 
            x="label_x", 
            y="faturamento", 
            color="executivo",
            color_discrete_sequence=px.colors.qualitative.Bold 
        )
        
        max_y_ex = base_exec_raw['faturamento'].max()
        tick_vals_x, tick_txt_x, y_cap_x = get_pretty_ticks(max_y_ex)
        
        fig_exec.update_layout(
            height=450, xaxis_title=None, yaxis_title=None, 
            template="plotly_white", showlegend=False,
            bargap=0.2
        )
        fig_exec.update_traces(width=0.5)

        fig_exec.update_yaxes(tickvals=tick_vals_x, ticktext=tick_txt_x, range=[0, y_cap_x])
        
        if show_labels:
            fig_exec.update_traces(text=base_exec_raw['faturamento'].apply(format_pt_br_abrev), textposition='outside')
            
        st.plotly_chart(fig_exec, width="stretch")
    else:
        st.info("Sem dados.")

    # ==================== SEÇÃO DE EXPORTAÇÃO ====================
    st.divider()
    def get_filter_string():
        f = st.session_state 
        ano_ini = f.get("filtro_ano_ini", "N/A")
        ano_fim = f.get("filtro_ano_fim", "N/A")
        emis = ", ".join(f.get("filtro_emis", ["Todas"]))
        execs = ", ".join(f.get("filtro_execs", ["Todos"]))
        meses = ", ".join(f.get("filtro_meses_lista", ["Todos"]))
        clientes = ", ".join(f.get("filtro_clientes", ["Todos"])) if f.get("filtro_clientes") else "Todos"
        return (f"Período (Ano): {ano_ini} a {ano_fim} | Meses: {meses} | "
                f"Emissoras: {emis} | Executivos: {execs} | Clientes: {clientes}")

    if st.button("📥 Exportar Dados da Página", type="secondary"):
        st.session_state.show_visao_geral_export = True
    
    if ultima_atualizacao:
        st.caption(f"📅 Última atualização da base de dados: {ultima_atualizacao}")

    if st.session_state.get("show_visao_geral_export", False):
        @st.dialog("Opções de Exportação - Visão Geral")
        def export_dialog():
            df_share_exp = pd.DataFrame()
            if not base_emis_raw.empty:
                df_share_exp = base_emis_raw.copy() 

            # MONTAGEM LINEAR DO DICIONÁRIO (COM NOMES REAIS)
            final_ordered_options = {}

            # 1. Evolução
            if not evol_raw.empty:
                final_ordered_options["1. Evolução Mensal de Faturamento e Inserções (Dados)"] = {'df': evol_raw}
                final_ordered_options["1. Evolução Mensal de Faturamento e Inserções (Gráfico)"] = {'fig': fig_evol}

            # 2. Emissora
            if not base_emis_raw.empty:
                final_ordered_options["2. Faturamento por Emissora (Dados)"] = {'df': base_emis_raw}
                final_ordered_options["2. Faturamento por Emissora (Gráfico)"] = {'fig': fig_emis if not base_emis_raw.empty else None}

            # 3. Share
            if not df_share_exp.empty:
                final_ordered_options["3. Share de Faturamento (Dados)"] = {'df': df_share_exp}
                # Adiciona as roscas individuais
                for name, fig in figs_share_dict.items():
                    final_ordered_options[name] = {'fig': fig}

            # 4. Executivo
            if not base_exec_raw.empty:
                final_ordered_options["4. Faturamento por Executivo (Dados)"] = {'df': base_exec_raw}
                final_ordered_options["4. Faturamento por Executivo (Gráfico)"] = {'fig': fig_exec if not base_exec_raw.empty else None}

            # Filtra apenas o que tem conteúdo válido
            available_options = [k for k, v in final_ordered_options.items() if (v.get('df') is not None and not v['df'].empty) or (v.get('fig') is not None)]
            
            if not available_options:
                st.warning("Nenhuma tabela ou gráfico com dados foi gerado.")
                if st.button("Fechar", type="secondary"):
                    st.session_state.show_visao_geral_export = False
                    st.rerun()
                return

            selected_names = st.multiselect("Selecione os itens para exportar:", options=available_options, default=available_options)
            
            tables_to_export = {name: final_ordered_options[name] for name in selected_names}

            if not tables_to_export:
                st.error("Selecione pelo menos um item.")
                return

            try:
                filtro_str = get_filter_string()
                # NOME DO ARQUIVO EXCEL INTERNO
                nome_interno_excel = "Dashboard_Visao_Geral.xlsx"
                
                zip_data = create_zip_package(tables_to_export, filtro_str, excel_filename=nome_interno_excel) 
                
                st.download_button("Clique para baixar o pacote", data=zip_data, file_name="Dashboard_VisaoGeral.zip", mime="application/zip", on_click=lambda: st.session_state.update(show_visao_geral_export=False), type="secondary")
            except Exception as e:
                st.error(f"Erro ao gerar ZIP: {e}")

            if st.button("Cancelar", key="cancel_export", type="secondary"):
                st.session_state.show_visao_geral_export = False
                st.rerun()
        export_dialog()