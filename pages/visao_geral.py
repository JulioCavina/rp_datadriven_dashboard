# pages/visao_geral.py

import streamlit as st
import plotly.express as px
from utils.format import brl, PALETTE
import pandas as pd
import plotly.graph_objects as go 
from plotly.subplots import make_subplots
import numpy as np
from utils.export import create_zip_package 

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
    magnitude = 10**np.floor(np.log10(ideal_interval))
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

def render(df, mes_ini, mes_fim, show_labels, ultima_atualizacao=None):
    st.header("Visão Geral")
    
    evol_raw = pd.DataFrame()
    base_emis_raw = pd.DataFrame()
    base_exec_raw = pd.DataFrame()
    fig_evol = go.Figure()
    fig_emis = go.Figure()
    fig_exec = go.Figure()
    fig_share = go.Figure()

    # ==================== PREPARAÇÃO DE DADOS ====================
    df = df.rename(columns={c: c.lower() for c in df.columns})

    # Garante existência da coluna insercoes para não quebrar
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

    # ==================== KPI LINHA 1: FINANCEIRO ====================
    totalA = float(baseA["faturamento"].sum()) if not baseA.empty else 0.0
    totalB = float(baseB["faturamento"].sum()) if not baseB.empty else 0.0
    delta_abs = totalB - totalA
    delta_pct = (delta_abs / totalA * 100) if totalA > 0.0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Total {ano_base}", format_pt_br_abrev(totalA))
    c2.metric(f"Total {ano_comp}", format_pt_br_abrev(totalB))
    c3.metric(f"Δ Absoluto ({ano_comp_str}-{ano_base_str})", format_pt_br_abrev(delta_abs))
    c4.metric(f"Δ % ({ano_comp_str} vs {ano_base_str})", f"{delta_pct:.2f}%" if totalA > 0 else "—")

    # ==================== KPI LINHA 2: ESTRATÉGICO (NOVO) ====================
    num_clientes = baseB["cliente"].nunique()
    ticket_medio = totalB / num_clientes if num_clientes > 0 else 0.0
    
    top_cli_series = baseB.groupby("cliente")["faturamento"].sum().sort_values(ascending=False)
    if not top_cli_series.empty:
        top_cli_nome = top_cli_series.index[0]
        top_cli_valor = top_cli_series.iloc[0]
        if len(top_cli_nome) > 22:
            top_cli_nome_display = top_cli_nome[:22] + "..."
        else:
            top_cli_nome_display = top_cli_nome
    else:
        top_cli_nome_display = "—"
        top_cli_valor = 0.0

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True) 
    
    k1, k2, k3 = st.columns(3)
    k1.metric(f"Clientes Ativos ({ano_comp})", num_clientes)
    k2.metric(f"Ticket Médio ({ano_comp})", format_pt_br_abrev(ticket_medio))
    
    k3.metric(
        label=f"Maior ({ano_comp}): {top_cli_nome_display}", 
        value=format_pt_br_abrev(top_cli_valor)
    )

    st.divider()

    # ==================== GRÁFICO 1: EVOLUÇÃO MENSAL (EIXO DUPLO) ====================
    st.markdown("<p class='custom-chart-title'>1. Evolução Mensal de Faturamento e Inserções</p>", unsafe_allow_html=True)
    
    evol_raw = base_periodo.groupby(["ano", "meslabel", "mes"], as_index=False)[["faturamento", "insercoes"]].sum().sort_values(["ano", "mes"])
    
    if not evol_raw.empty:
        fig_evol = make_subplots(specs=[[{"secondary_y": True}]])

        # 1. Barras de Faturamento (Eixo Esquerdo - Azul)
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

        # 2. Linha de Inserções (Eixo Direito - Vermelho)
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

        # Configuração de Eixos
        max_y_fat = evol_raw['faturamento'].max()
        tick_vals, tick_txt, y_cap_fat = get_pretty_ticks(max_y_fat)
        
        fig_evol.update_yaxes(
            title_text="Faturamento (R$)", 
            tickvals=tick_vals, 
            ticktext=tick_txt, 
            range=[0, y_cap_fat], 
            secondary_y=False,
            showgrid=True, 
            gridcolor='#f0f0f0'
        )
        
        max_y_ins = evol_raw['insercoes'].max()
        y_cap_ins = max_y_ins * 1.2 if max_y_ins > 0 else 10
        fig_evol.update_yaxes(
            title_text="Inserções (Qtd)", 
            range=[0, y_cap_ins], 
            secondary_y=True,
            showgrid=False
        )

        fig_evol.update_layout(
            height=400, 
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"), 
            template="plotly_white",
            margin=dict(l=20, r=20, t=20, b=20)
        )
        
        # Rótulos de Dados
        if show_labels:
            for i, row in evol_raw.iterrows():
                # Rótulo Faturamento (Caixa Branca)
                fig_evol.add_annotation(
                    x=row["meslabel"], 
                    y=row["faturamento"], 
                    text=format_pt_br_abrev(row["faturamento"]),
                    showarrow=False, 
                    yshift=10, 
                    font=dict(size=10, color="black"),
                    bgcolor="rgba(255, 255, 255, 0.8)", 
                    borderpad=2,
                    secondary_y=False
                )
                
                # Rótulo Inserções (Agora com estilo de caixa e posicionado corretamente)
                if row["insercoes"] > 0:
                    fig_evol.add_annotation(
                        x=row["meslabel"], 
                        y=row["insercoes"], 
                        text=str(int(row["insercoes"])),
                        showarrow=False, 
                        yshift=15, 
                        font=dict(size=10, color="#dc2626", weight="bold"),
                        bgcolor="rgba(255, 255, 255, 0.7)", # Fundo transparente igual ao pedido
                        borderpad=2,
                        yref="y2", # FORÇA O USO DO EIXO SECUNDÁRIO PARA POSICIONAMENTO
                        secondary_y=True
                    )

        st.plotly_chart(fig_evol, width="stretch") 
    else:
        st.info("Sem dados para o período selecionado.")

    st.divider()

    # ==================== GRÁFICOS INFERIORES ====================
    colA, colB, colC = st.columns([1.3, 1, 1.3])

    base_emis_raw = base_periodo.groupby("emissora", as_index=False)["faturamento"].sum().sort_values("faturamento", ascending=False)

    with colA:
        st.markdown("<p class='custom-chart-title'>2. Faturamento por Emissora</p>", unsafe_allow_html=True)
        if not base_emis_raw.empty:
            fig_emis = px.bar(base_emis_raw, x="emissora", y="faturamento", color_discrete_sequence=[PALETTE[0]])
            max_y_emis = base_emis_raw['faturamento'].max()
            tick_vals_e, tick_txt_e, y_cap_e = get_pretty_ticks(max_y_emis)
            fig_emis.update_layout(height=350, xaxis_title=None, yaxis_title=None, template="plotly_white")
            fig_emis.update_yaxes(tickvals=tick_vals_e, ticktext=tick_txt_e, range=[0, y_cap_e])
            if show_labels:
                fig_emis.update_traces(text=base_emis_raw['faturamento'].apply(format_pt_br_abrev), textposition='outside')
            st.plotly_chart(fig_emis, width="stretch")
        else:
            st.info("Sem dados.")

    with colB:
        st.markdown("<p class='custom-chart-title'>3. Share Faturamento (%)</p>", unsafe_allow_html=True)
        if not base_emis_raw.empty:
            fig_share = px.pie(
                base_emis_raw, 
                values="faturamento", 
                names="emissora",
                color_discrete_sequence=PALETTE,
                hole=0.5
            )
            fig_share.update_traces(textposition='inside', textinfo='percent+label')
            fig_share.update_layout(height=350, showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_share, width="stretch")
        else:
            st.info("Sem dados.")

    with colC:
        st.markdown("<p class='custom-chart-title'>4. Faturamento por Executivo</p>", unsafe_allow_html=True)
        base_exec_raw = base_periodo.groupby("executivo", as_index=False)["faturamento"].sum().sort_values("faturamento", ascending=False)
        if not base_exec_raw.empty:
            fig_exec = px.bar(base_exec_raw, x="executivo", y="faturamento", color_discrete_sequence=[PALETTE[3]])
            max_y_ex = base_exec_raw['faturamento'].max()
            tick_vals_x, tick_txt_x, y_cap_x = get_pretty_ticks(max_y_ex)
            fig_exec.update_layout(height=350, xaxis_title=None, yaxis_title=None, template="plotly_white")
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
            df_share = pd.DataFrame()
            if not base_emis_raw.empty:
                df_share = base_emis_raw.copy()
                total_share = df_share["faturamento"].sum()
                df_share["Share %"] = (df_share["faturamento"] / total_share) if total_share > 0 else 0.0

            all_options = {
                "1. Evolução Mensal (Dados)": {'df': evol_raw},
                "1. Evolução Mensal (Gráfico)": {'fig': fig_evol}, 
                "2. Fat. por Emissora (Dados)": {'df': base_emis_raw},
                "2. Fat. por Emissora (Gráfico)": {'fig': fig_emis},
                "3. Share Emissora (Dados)": {'df': df_share},  
                "3. Share Emissora (Gráfico)": {'fig': fig_share},
                "4. Fat. por Executivo (Dados)": {'df': base_exec_raw},
                "4. Fat. por Executivo (Gráfico)": {'fig': fig_exec},
            }
            available_options = [name for name, data in all_options.items() if (data.get('df') is not None and not data['df'].empty) or (data.get('fig') is not None and data['fig'].data)]
            
            if not available_options:
                st.warning("Nenhuma tabela ou gráfico com dados foi gerado.")
                if st.button("Fechar", type="secondary"):
                    st.session_state.show_visao_geral_export = False
                    st.rerun()
                return

            st.write("Selecione os itens para exportar:")
            selected_names = st.multiselect("Itens", options=available_options, default=available_options)
            
            tables_to_export = {name: all_options[name] for name in selected_names}

            if not tables_to_export:
                st.error("Selecione pelo menos um item.")
                return

            try:
                filtro_str = get_filter_string()
                zip_data = create_zip_package(tables_to_export, filtro_str) 
                st.download_button("Clique para baixar o pacote", data=zip_data, file_name="Dashboard_VisaoGeral.zip", mime="application/zip", on_click=lambda: st.session_state.update(show_visao_geral_export=False), type="secondary")
            except Exception as e:
                st.error(f"Erro ao gerar ZIP: {e}")

            if st.button("Cancelar", key="cancel_export", type="secondary"):
                st.session_state.show_visao_geral_export = False
                st.rerun()
        export_dialog()