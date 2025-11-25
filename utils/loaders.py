# utils/loaders.py
import os
import pandas as pd
import streamlit as st
from datetime import datetime
from .format import normalize_dataframe

def load_main_base():
    """
    Carrega a base principal.
    Prioridade:
    1. Procura em st.session_state (se o usuário fez upload).
    2. Procura na pasta /data (arquivo .xlsx).
    Retorna (df, data_modificação) ou (None, None) se nada for encontrado.
    """
    
    # --- 1. Verifica se o usuário já fez upload de um arquivo nesta sessão ---
    if "uploaded_dataframe" in st.session_state and st.session_state.uploaded_dataframe is not None:
        df = st.session_state.uploaded_dataframe
        data_modificacao = st.session_state.get("uploaded_timestamp", "Sessão Atual")
        return df, data_modificacao

    # --- 2. Se não houver, procura na pasta /data ---
    base_dir = os.path.dirname(os.path.dirname(__file__)) 
    data_dir = os.path.join(base_dir, "data")

    if not os.path.exists(data_dir):
        os.makedirs(data_dir) # Cria a pasta se não existir

    try:
        excel_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".xlsx")]
    except FileNotFoundError:
        st.error(f"❌ Erro: O diretório '{data_dir}' não foi encontrado.")
        return None, None

    if excel_files:
        file_path = os.path.join(data_dir, excel_files[0]) # Pega o primeiro .xlsx que encontrar
        try:
            df_raw = pd.read_excel(file_path, engine="openpyxl")
            df = normalize_dataframe(df_raw)
            if df.empty:
                st.warning("⚠️ Base encontrada, mas sem dados válidos.")
                return None, None

            # --- NOVA LÓGICA: PEGAR ÚLTIMO MÊS/ANO DA BASE ---
            ultima_atualizacao = "N/A" 
            if "data_ref" in df.columns and pd.api.types.is_datetime64_any_dtype(df["data_ref"]):
                
                # Pega a data mais recente válida
                latest_date = df["data_ref"].max()
                
                if pd.notna(latest_date):
                    latest_month = latest_date.month
                    latest_year = latest_date.year
                    # Formata como MM/YYYY (02d garante o zero à esquerda)
                    ultima_atualizacao = f"{latest_month:02d}/{latest_year}"
                else:
                    ultima_atualizacao = "Data Inválida"

            else:
                # Fallback para o tempo de modificação do arquivo se data_ref não estiver disponível
                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                ultima_atualizacao = mod_time.strftime("%d/%m/%Y")
            # --- FIM DA NOVA LÓGICA ---

            # Salva no cache da sessão para não precisar ler do disco toda hora
            st.session_state.uploaded_dataframe = df
            st.session_state.uploaded_timestamp = ultima_atualizacao
            
            return df, ultima_atualizacao
        
        except Exception as e:
            st.error(f"Erro ao ler base {file_path}: {e}")
            return None, None

    # --- 3. Se não encontrou em nenhum lugar ---
    return None, None


def load_crowley_base():
    """Placeholder para base Crowley (não usada atualmente)."""
    return None, None