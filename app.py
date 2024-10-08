import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from folium.plugins import MarkerCluster
import plotly.express as px

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
                    'lt_desc': f"{linha['lt0']} - {linha['lt1']}",
                    'terminal': identificar_terminal(veiculo['py'], veiculo['px'])
                })
                veiculos.append(veiculo)
        df = pd.DataFrame(veiculos)
        df['latitude'] = df['py']
        df['longitude'] = df['px']
        df['ativo'] = df['a']
        df['ultima_atualizacao'] = pd.to_datetime(df['ta'])
        return df[['latitude', 'longitude', 'p', 'ativo', 'ultima_atualizacao', 'lt_desc', 'cl', 'terminal']]
    return pd.DataFrame()

# Função para identificar terminais conhecidos por coordenadas (manual)
def identificar_terminal(lat, lon):
    terminais = {
        (-23.5211, -46.6828): "Terminal Barra Funda",
        (-23.5505, -46.6333): "Terminal São Paulo",
        (-23.6028, -46.7351): "Terminal Jabaquara",
        (-23.4789, -46.6267): "Terminal Santana"
    }
    for (t_lat, t_lon), nome_terminal in terminais.items():
        if abs(lat - t_lat) < 0.001 and abs(lon - t_lon) < 0.001:
            return nome_terminal
    return "Local desconhecido"

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
            <b>Última atualização:</b> {row['ultima_atualizacao']}<br>
            <b>Terminal:</b> {row['terminal']}
        </div>
        """
        icon = folium.Icon(color='blue', icon='bus', prefix='fa')
        folium.Marker(
            [row['latitude'], row['longitude']],
            popup=folium.Popup(popup_content, max_width=400),
            icon=icon
        ).add_to(marker_cluster)

    return mapa

# Função para exibir gráficos dinâmicos usando Plotly
def exibir_graficos(df_onibus):
    st.subheader("Análises Gráficas")
    col1, col2 = st.columns(2)

    # Gráfico de Distribuição de Ônibus Ativos e Inativos
    with col1:
        status_counts = df_onibus['ativo'].value_counts()
        fig = px.bar(
            x=status_counts.index.map({True: 'Ativos', False: 'Inativos'}),
            y=status_counts.values,
            labels={'x': 'Status', 'y': 'Quantidade'},
            title='Ônibus Ativos vs Inativos',
            color=status_counts.index.map({True: 'Ativos', False: 'Inativos'}),
            color_discrete_map={'Ativos': 'green', 'Inativos': 'red'}
        )
        st.plotly_chart(fig, use_container_width=True)

    # Gráfico de Distribuição de Ônibus por Linha
    with col2:
        linhas_counts = df_onibus['lt_desc'].value_counts().head(5)
        fig2 = px.bar(
            x=linhas_counts.values,
            y=linhas_counts.index,
            orientation='h',
            labels={'x': 'Número de Ônibus', 'y': 'Linhas'},
            title='Top 5 Linhas com Mais Ônibus'
        )
        st.plotly_chart(fig2, use_container_width=True)

# Função principal
def main():
    st.set_page_config(layout="wide")
    st.title("Localização dos Ônibus")

    if autenticar_api(API_TOKEN):
        dados = obter_dados_onibus()
        if dados:
            df_onibus = transformar_dados_em_dataframe(dados)

            if not df_onibus.empty:
                # Calcular totais gerais para o painel de controle
                total_onibus_geral = len(df_onibus)
                total_ativos_geral = df_onibus['ativo'].sum()
                total_inativos_geral = total_onibus_geral - total_ativos_geral
                ultima_atualizacao_geral = df_onibus['ultima_atualizacao'].max()

                # Obter as linhas disponíveis para o selectbox
                linhas_disponiveis = df_onibus['lt_desc'].unique().tolist()
                linha_selecionada = st.selectbox("Selecione a linha de ônibus", options=linhas_disponiveis)

                # Filtro de status dos ônibus (ativos/inativos)
                status_selecionado = st.sidebar.selectbox(
                    "Filtrar por Status",
                    options=["Todos", "Ativos", "Inativos"]
                )

                # Filtrar o DataFrame pela linha e status selecionado
                df_filtrado = df_onibus[df_onibus['lt_desc'] == linha_selecionada]

                if status_selecionado == "Ativos":
                    df_filtrado = df_filtrado[df_filtrado['ativo']]
                elif status_selecionado == "Inativos":
                    df_filtrado = df_filtrado[~df_filtrado['ativo']]

                # Painel de controle com métricas gerais
                st.sidebar.header("Painel de Controle")
                st.sidebar.metric("Total de Ônibus", total_onibus_geral)
                st.sidebar.metric("Ônibus Ativos", total_ativos_geral)
                st.sidebar.metric("Ônibus Inativos", total_inativos_geral)
                st.sidebar.metric("Última Atualização", ultima_atualizacao_geral.strftime("%Y-%m-%d %H:%M:%S"))

                # Exibir o mapa com os ônibus filtrados
                if not df_filtrado.empty:
                    mapa = criar_mapa_com_clusters(df_filtrado)
                    st_folium(mapa, width='100%')
                    st.write(f"Total de ônibus plotados: {len(df_filtrado)}")
                else:
                    st.warning("Nenhum dado de ônibus disponível para exibir no mapa.")

                # Exibir gráficos dinâmicos abaixo do mapa
                exibir_graficos(df_onibus)

            else:
                st.warning("Nenhum dado de ônibus disponível.")
        else:
            st.error("Falha ao obter dados dos ônibus.")
    else:
        st.error("Falha na autenticação com a API SPTrans.")

if __name__ == "__main__":
    main()
