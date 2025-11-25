# pages/cruzamentos_intersecoes.py

import streamlit as st
import pandas as pd
import numpy as np
from utils.format import brl, PALETTE
import plotly.graph_objects as go
import plotly.express as px
from itertools import combinations
from utils.export import create_zip_package 

def format_int(val):
    """Formata inteiros com separador de milhar."""
    if pd.isna(val) or val == 0: return "-"
    return f"{int(val):,}".replace(",", ".")

def render(df, mes_ini, mes_fim, show_labels, ultima_atualizacao=None):
    def format_pt_br_abrev(val):
        if pd.isna(val) or val == 0: return brl(0) 
        if val >= 1_000_000: return f"R$ {val/1_000_000:,.1f} Mi"
        if val >= 1_000: return f"R$ {val/1_000:,.0f} mil"
        return brl(val)

    # ==================== TÍTULO CENTRALIZADO ====================
    st.markdown("<h2 style='text-align: center; color: #003366;'>Cruzamentos & Interseções entre Emissoras</h2>", unsafe_allow_html=True)
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # Inicialização para exportação
    df_excl_raw = pd.DataFrame()
    df_comp_raw = pd.DataFrame()
    top_shared_raw = pd.DataFrame()
    mat_raw = pd.DataFrame()
    fig_mat = go.Figure() 

    df = df.rename(columns={c: c.lower() for c in df.columns})

    if "cliente" not in df.columns or "emissora" not in df.columns or "faturamento" not in df.columns:
        st.error("Colunas obrigatórias 'Cliente', 'Emissora' e 'Faturamento' ausentes.")
        return
    
    if "insercoes" not in df.columns:
        df["insercoes"] = 0.0

    base_periodo = df[df["mes"].between(mes_ini, mes_fim)]

    if base_periodo.empty:
        st.info("Sem dados para o período selecionado.")
        return

    # Agrupamento Base (Adicionado Inserções)
    agg = base_periodo.groupby(["cliente", "emissora"], as_index=False).agg(
        faturamento=("faturamento", "sum"),
        insercoes=("insercoes", "sum")
    )
    agg["presenca"] = np.where(agg["faturamento"] > 0, 1, 0)

    # Pivôs para cálculos
    pres_pivot = agg.pivot_table(index="cliente", columns="emissora", values="presenca", fill_value=0)
    val_pivot = agg.pivot_table(index="cliente", columns="emissora", values="faturamento", fill_value=0.0) 
    ins_pivot = agg.pivot_table(index="cliente", columns="emissora", values="insercoes", fill_value=0.0)
    
    # Contagem de Emissoras por Cliente
    emis_count = pres_pivot.sum(axis=1)
    

    # ==================== CÁLCULOS EXCLUSIVOS VS COMPARTILHADOS ====================
    exclusivos_mask = emis_count == 1
    compartilhados_mask = emis_count >= 2

    excl_info, comp_info = [], []
    emissoras = sorted(agg["emissora"].unique())
    fat_total_geral = 0.0 

    for emis in emissoras:
        # --- EXCLUSIVOS ---
        cli_excl = pres_pivot.loc[exclusivos_mask & (pres_pivot[emis] == 1)].index
        # Filtra na base agregada
        dados_excl = agg[(agg["cliente"].isin(cli_excl)) & (agg["emissora"] == emis)]
        
        fat_excl = dados_excl["faturamento"].sum()
        ins_excl = dados_excl["insercoes"].sum()
        
        # --- COMPARTILHADOS ---
        cli_comp = pres_pivot.loc[compartilhados_mask & (pres_pivot[emis] == 1)].index
        dados_comp = agg[(agg["cliente"].isin(cli_comp)) & (agg["emissora"] == emis)]
        
        fat_comp = dados_comp["faturamento"].sum()
        ins_comp = dados_comp["insercoes"].sum()
        
        # Totais da Emissora
        dados_total = agg[agg["emissora"] == emis]
        fat_total = dados_total["faturamento"].sum()
        fat_total_geral += fat_total 
        
        excl_info.append({
            "Emissora": emis, 
            "Clientes Exclusivos": len(cli_excl),
            "Faturamento Exclusivo": fat_excl, 
            "Inserções Exclusivas": ins_excl,
            "% Faturamento": (fat_excl / fat_total * 100) if fat_total > 0 else 0
        })
        comp_info.append({
            "Emissora": emis, 
            "Clientes Compartilhados": len(cli_comp),
            "Faturamento Compartilhado": fat_comp, 
            "Inserções Compartilhadas": ins_comp,
            "% Faturamento": (fat_comp / fat_total * 100) if fat_total > 0 else 0
        })

    # ==================== 1. EXCLUSIVOS ====================
    st.subheader("1. Clientes Exclusivos por Emissora")
    df_excl_raw = pd.DataFrame(excl_info) 
    if not df_excl_raw.empty:
        df_excl_raw = df_excl_raw.sort_values("Faturamento Exclusivo", ascending=False).reset_index(drop=True)
        
        # Totalizador
        total_row = {
            "Emissora": "Totalizador", 
            "Clientes Exclusivos": df_excl_raw["Clientes Exclusivos"].sum(), 
            "Faturamento Exclusivo": df_excl_raw["Faturamento Exclusivo"].sum(), 
            "Inserções Exclusivas": df_excl_raw["Inserções Exclusivas"].sum(),
            "% Faturamento": (df_excl_raw["Faturamento Exclusivo"].sum() / fat_total_geral * 100) if fat_total_geral > 0 else np.nan
        }
        df_excl_raw = pd.concat([df_excl_raw, pd.DataFrame([total_row])], ignore_index=True)
        df_excl_raw.insert(0, "#", list(range(1, len(df_excl_raw))) + ["Total"])
        
        df_excl_display = df_excl_raw.copy()
        df_excl_display['#'] = df_excl_display['#'].astype(str)
        df_excl_display["Faturamento Exclusivo"] = df_excl_display["Faturamento Exclusivo"].apply(brl)
        df_excl_display["Inserções Exclusivas"] = df_excl_display["Inserções Exclusivas"].apply(format_int)
        df_excl_display["% Faturamento"] = df_excl_display["% Faturamento"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
        
        st.dataframe(df_excl_display, width='stretch', hide_index=True, column_config={"#": None})
    else: st.info("Nenhum cliente exclusivo encontrado.")
    st.divider()

    # ==================== 2. COMPARTILHADOS ====================
    st.subheader("2. Clientes Compartilhados por Emissora")
    df_comp_raw = pd.DataFrame(comp_info) 
    if not df_comp_raw.empty:
        df_comp_raw = df_comp_raw.sort_values("Faturamento Compartilhado", ascending=False).reset_index(drop=True)
        
        # Totalizador
        total_row = {
            "Emissora": "Totalizador", 
            "Clientes Compartilhados": df_comp_raw["Clientes Compartilhados"].sum(), 
            "Faturamento Compartilhado": df_comp_raw["Faturamento Compartilhado"].sum(), 
            "Inserções Compartilhadas": df_comp_raw["Inserções Compartilhadas"].sum(),
            "% Faturamento": (df_comp_raw["Faturamento Compartilhado"].sum() / fat_total_geral * 100) if fat_total_geral > 0 else np.nan
        }
        df_comp_raw = pd.concat([df_comp_raw, pd.DataFrame([total_row])], ignore_index=True)
        df_comp_raw.insert(0, "#", list(range(1, len(df_comp_raw))) + ["Total"])
        
        df_comp_display = df_comp_raw.copy()
        df_comp_display['#'] = df_comp_display['#'].astype(str)
        df_comp_display["Faturamento Compartilhado"] = df_comp_display["Faturamento Compartilhado"].apply(brl)
        df_comp_display["Inserções Compartilhadas"] = df_comp_display["Inserções Compartilhadas"].apply(format_int)
        df_comp_display["% Faturamento"] = df_comp_display["% Faturamento"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
        
        st.dataframe(df_comp_display, width='stretch', hide_index=True, column_config={"#": None})
    else: st.info("Nenhum cliente compartilhado encontrado.")
    st.divider()

    # ==================== 3. TOP CLIENTES COMPARTILHADOS ====================
    st.subheader("3. Top clientes compartilhados (2+ emissoras)")
    if compartilhados_mask.any():
        share_clients_idx = pres_pivot[compartilhados_mask].index
        
        # Ordenação personalizada
        custom_order = ["Difusora", "Novabrasil", "Th+ Prime", "Thathi Tv"]
        order_map = {name.lower(): i for i, name in enumerate(custom_order)}

        def get_emissoras_str(row):
            emis_ativas = row.index[row == 1].tolist()
            emis_ativas.sort(key=lambda x: (order_map.get(x.lower(), 999), x))
            return ", ".join(emis_ativas)

        df_emis_list = pres_pivot.loc[share_clients_idx].apply(get_emissoras_str, axis=1)
        
        # Agrupa Faturamento e Inserções
        top_shared_raw = (base_periodo[base_periodo["cliente"].isin(share_clients_idx)]
                          .groupby("cliente", as_index=False)
                          .agg(faturamento=("faturamento", "sum"), insercoes=("insercoes", "sum"))
                          .sort_values("faturamento", ascending=False)
                          .head(20))
        
        top_shared_raw["emissoras_compartilhadas"] = top_shared_raw["cliente"].map(df_emis_list)

        if not top_shared_raw.empty:
            top_shared_raw = pd.concat([
                top_shared_raw, 
                pd.DataFrame([{
                    "cliente": "Totalizador", 
                    "faturamento": top_shared_raw["faturamento"].sum(),
                    "insercoes": top_shared_raw["insercoes"].sum(),
                    "emissoras_compartilhadas": "" 
                }])
            ], ignore_index=True)
        
        top_shared_raw.insert(0, "#", list(range(1, len(top_shared_raw))) + ["Total"])
        
        top_shared_disp = top_shared_raw.copy().rename(columns={
            "cliente": "Cliente", 
            "faturamento": "Faturamento",
            "insercoes": "Inserções",
            "emissoras_compartilhadas": "Emissoras Compartilhadas"
        })
        
        top_shared_disp['#'] = top_shared_disp['#'].astype(str)
        top_shared_disp["Faturamento"] = top_shared_disp["Faturamento"].apply(brl)
        top_shared_disp["Inserções"] = top_shared_disp["Inserções"].apply(format_int)
        
        st.dataframe(top_shared_disp, width="stretch", hide_index=True, column_config={"#": None})
    else: st.info("Não há clientes compartilhados com os filtros atuais.")
    st.divider()

    # ==================== 4. MATRIZ DE INTERSEÇÃO ====================
    if "cruzamentos_metric" not in st.session_state: st.session_state.cruzamentos_metric = "Clientes"
    metric = st.session_state.cruzamentos_metric
    
    btn_label_clientes = "Clientes em comum"
    btn_label_fat = "Faturamento em comum (R$)"
    btn_label_ins = "Inserções em comum (Qtd)"
    
    metric_label = metric 
    if metric == "Clientes": metric_label = btn_label_clientes
    elif metric == "Faturamento": metric_label = btn_label_fat
    else: metric_label = btn_label_ins
    
    st.subheader(f"4. Interseções entre emissoras (matriz) - {metric_label}")
    emis_list = sorted(list(pres_pivot.columns))
    
    if len(emis_list) < 2:
        st.info("Requer pelo menos 2 emissoras para cruzamento.")
    else:
        # Botões - agora são 3 opções
        col1, col2, col3 = st.columns([1, 1, 1]) 
        
        btn_type_clientes = "primary" if metric == "Clientes" else "secondary"
        btn_type_fat = "primary" if metric == "Faturamento" else "secondary"
        btn_type_ins = "primary" if metric == "Insercoes" else "secondary"
        
        with col1:
            if st.button(btn_label_clientes, type=btn_type_clientes, use_container_width=True):
                st.session_state.cruzamentos_metric = "Clientes"
                st.rerun() 
        with col2:
            if st.button(btn_label_fat, type=btn_type_fat, use_container_width=True):
                st.session_state.cruzamentos_metric = "Faturamento"
                st.rerun() 
        with col3:
            if st.button(btn_label_ins, type=btn_type_ins, use_container_width=True):
                st.session_state.cruzamentos_metric = "Insercoes"
                st.rerun() 

        mat_raw = pd.DataFrame(0.0, index=emis_list, columns=emis_list)
        z_text = None 
        text_colors_2d = [] 

        # --- Lógica da Matriz ---
        if metric == "Clientes":
            for a, b in combinations(emis_list, 2):
                comuns = ((pres_pivot[a] == 1) & (pres_pivot[b] == 1)).sum()
                mat_raw.loc[a, b] = comuns
                mat_raw.loc[b, a] = comuns
            for e in emis_list: mat_raw.loc[e, e] = (pres_pivot[e] == 1).sum()
            z = mat_raw.values
            hover = "<b>%{y} x %{x}</b><br>Clientes: %{z}<extra></extra>"
            z_text = z.astype(int).astype(str) 
            max_val = np.nanmax(z) if z.size > 0 else 0
            text_colors_2d = [['white' if v > max_val * 0.4 else 'black' for v in row] for row in z]
            
        elif metric == "Faturamento": 
            for a, b in combinations(emis_list, 2):
                menor = np.minimum(val_pivot[a], val_pivot[b])
                vlr = menor[menor > 0].sum()
                mat_raw.loc[a, b] = vlr
                mat_raw.loc[b, a] = vlr
            for e in emis_list: mat_raw.loc[e, e] = val_pivot[e].sum()
            z = mat_raw.values
            hover = "<b>%{y} x %{x}</b><br>Valor: R$ %{z:,.2f}<extra></extra>"
            z_text = [[format_pt_br_abrev(v) for v in row] for row in z]
            max_val = np.nanmax(z) if z.size > 0 else 0
            text_colors_2d = [['white' if v > max_val * 0.4 else 'black' for v in row] for row in z]
            
        else: # Inserções
            for a, b in combinations(emis_list, 2):
                # Interseção de Inserções (Mínimo entre as duas)
                menor = np.minimum(ins_pivot[a], ins_pivot[b])
                vlr = menor[menor > 0].sum()
                mat_raw.loc[a, b] = vlr
                mat_raw.loc[b, a] = vlr
            for e in emis_list: mat_raw.loc[e, e] = ins_pivot[e].sum()
            z = mat_raw.values
            hover = "<b>%{y} x %{x}</b><br>Inserções: %{z:,.0f}<extra></extra>"
            z_text = [[format_int(v) for v in row] for row in z]
            max_val = np.nanmax(z) if z.size > 0 else 0
            text_colors_2d = [['white' if v > max_val * 0.4 else 'black' for v in row] for row in z]

        fig_mat = go.Figure(data=go.Heatmap(z=z, x=mat_raw.columns, y=mat_raw.index, colorscale="Blues", hovertemplate=hover, showscale=True))
        if show_labels and z_text is not None:
            for i, row in enumerate(z):
                for j, val in enumerate(row):
                    fig_mat.add_annotation(x=mat_raw.columns[j], y=mat_raw.index[i], text=z_text[i][j], showarrow=False, font=dict(color=text_colors_2d[i][j]))

        fig_mat.update_layout(height=420, template="plotly_white", margin=dict(l=0, r=10, t=10, b=0))
        st.plotly_chart(fig_mat, width="stretch")
        
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
        st.session_state.show_cruzamentos_export = True
    
    if ultima_atualizacao:
        st.caption(f"📅 Última atualização da base de dados: {ultima_atualizacao}")

    if st.session_state.get("show_cruzamentos_export", False):
        @st.dialog("Opções de Exportação - Cruzamentos")
        def export_dialog():
            # Prepara DFs para exportação com nomes bonitos
            table_options = {
                "1. Clientes Exclusivos": {'df': df_excl_raw},
                "2. Clientes Compartilhados": {'df': df_comp_raw},
                "3. Top Compartilhados": {'df': top_shared_raw},
                "4. Matriz (Dados)": {'df': mat_raw.reset_index().rename(columns={'index':'Emissora'})},
                "4. Matriz (Gráfico)": {'fig': fig_mat} 
            }
            
            available_options = [name for name, data in table_options.items() if (data.get('df') is not None and not data['df'].empty) or (data.get('fig') is not None and data['fig'].data)]
            
            if not available_options:
                st.warning("Nenhuma tabela com dados foi gerada.")
                if st.button("Fechar", type="secondary"):
                    st.session_state.show_cruzamentos_export = False
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
                st.download_button("Clique para baixar", data=zip_data, file_name="Dashboard_Cruzamentos.zip", mime="application/zip", on_click=lambda: st.session_state.update(show_cruzamentos_export=False), type="secondary")
            except Exception as e:
                st.error(f"Erro ao gerar ZIP: {e}")

            if st.button("Cancelar", key="cancel_export", type="secondary"):
                st.session_state.show_cruzamentos_export = False
                st.rerun()
        export_dialog()