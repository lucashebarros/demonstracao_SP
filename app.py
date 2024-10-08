import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from folium.plugins import MarkerCluster

# Substitua pelo seu token
API_TOKEN = 'edfe25257c6da1492d01022aec83cd8c360c9bedde6636d16fd092692a57862c'

# Criar uma sessão global para manter cookies e autenticação
session = requests.Session()

# Função para autenticação na API
def autenticar_api(token):
    url = f"http://api.olhovivo.sptrans.com.br/v2.1/Login/Autenticar?token={token}"
    try:
        response = session.post(url, timeout=30)
        return response.status_code == 200 and response.json() is True
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao autenticar na API: {e}")
    return False

# Função para obter dados dos ônibus em tempo real
@st.cache_data(ttl=300)  # Cache dos dados por 5 minutos
def obter_dados_onibus():
    url = "http://api.olhovivo.sptrans.com.br/v2.1/Posicao"
    try:
        response = session.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao acessar a API: {e}")
    return None

# Função para transformar dados em DataFrame
def transformar_dados_em_dataframe(dados):
    if 'l' in dados:
        veiculos = []
        for linha in dados['l']:
            for veiculo in linha.get('vs', []):
                veiculo.update({
                    'cl': linha['cl'],
                    'lt_desc': f"{linha['lt0']} - {linha['lt1']}"
                })
                veiculos.append(veiculo)
        df = pd.DataFrame(veiculos)
        df['latitude'] = df['py']
        df['longitude'] = df['px']
        df['ativo'] = df['a']
        df['ultima_atualizacao'] = pd.to_datetime(df['ta'])
        return df[['latitude', 'longitude', 'p', 'ativo', 'ultima_atualizacao', 'lt_desc', 'cl']]
    return pd.DataFrame()

# Função para criar um mapa com clusters
def criar_mapa_com_clusters(df_onibus):
    mapa = folium.Map(zoom_start=12, location=[-23.55052, -46.633308], tiles="cartodb dark_matter")
    marker_cluster = MarkerCluster().add_to(mapa)

    for _, row in df_onibus.iterrows():
        popup_content = f"""
        <div style="width: 300px; font-size: 14px;">
            <b>Código do Ônibus:</b> {row['p']}<br>
            <b>Ativo:</b> {"Sim" if row['ativo'] else "Não"}<br>
            <b>Linha:</b> {row['lt_desc']}<br>
            <b>Última atualização:</b> {row['ultima_atualizacao']}
        </div>
        """
        icon = folium.Icon(color='blue', icon='bus', prefix='fa')
        folium.Marker(
            [row['latitude'], row['longitude']],
            popup=folium.Popup(popup_content, max_width=400),
            icon=icon
        ).add_to(marker_cluster)

    return mapa

# Função principal
def main():
    st.set_page_config(layout="wide")
    st.title("Localização dos Ônibus")

    if autenticar_api(API_TOKEN):
        dados = obter_dados_onibus()
        if dados:
            df_onibus = transformar_dados_em_dataframe(dados)

            if not df_onibus.empty:
                # Obter as linhas disponíveis para o selectbox e adicionar a opção "Todos"
                linhas_disponiveis = ['Todos'] + df_onibus['lt_desc'].unique().tolist()
                linha_selecionada = st.selectbox("Selecione a linha de ônibus", options=linhas_disponiveis)

                # Filtrar o DataFrame pela linha selecionada, se não for "Todos"
                if linha_selecionada != 'Todos':
                    df_filtrado = df_onibus[df_onibus['lt_desc'] == linha_selecionada]
                else:
                    df_filtrado = df_onibus

                # Painel de controle com métricas
                total_onibus = len(df_filtrado)
                total_ativos = df_filtrado['ativo'].sum()
                total_inativos = total_onibus - total_ativos
                ultima_atualizacao = df_filtrado['ultima_atualizacao'].max()

                st.sidebar.header("Painel de Controle")
                st.sidebar.metric("Total de Ônibus", total_onibus)
                st.sidebar.metric("Ônibus Ativos", total_ativos)
                st.sidebar.metric("Ônibus Inativos", total_inativos)
                st.sidebar.metric("Última Atualização", ultima_atualizacao.strftime("%Y-%m-%d %H:%M:%S"))

                # Exibir o mapa com os ônibus filtrados
                if not df_filtrado.empty:
                    mapa = criar_mapa_com_clusters(df_filtrado)
                    st_folium(mapa, width='100%')
                    st.write(f"Total de ônibus plotados: {len(df_filtrado)}")
                else:
                    st.warning("Nenhum dado de ônibus disponível para exibir no mapa.")
            else:
                st.warning("Nenhum dado de ônibus disponível.")
        else:
            st.error("Falha ao obter dados dos ônibus.")
    else:
        st.error("Falha na autenticação com a API SPTrans.")

if __name__ == "__main__":
    main()
