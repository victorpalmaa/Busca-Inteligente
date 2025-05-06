import streamlit as st
import pandas as pd
import plotly.express as px
import logging
from scraper import SupplementScraper
from io import BytesIO
from datetime import datetime
from PIL import Image
from time import sleep
import base64

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuração da página Streamlit
st.set_page_config(
    page_title="ProNutrition Busca Inteligente",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# Carregar o logo
try:
    logo = Image.open("img/logo-pronutrition.png")
    base_width = 150
    w_percent = (base_width / float(logo.size[0]))
    h_size = int((float(logo.size[1]) * float(w_percent)))
    logo = logo.resize((base_width, h_size), Image.Resampling.LANCZOS)
    
    # Converter a imagem para base64 mantendo o formato PNG
    buffered = BytesIO()
    logo.save(buffered, format="PNG", optimize=True)
    logo_base64 = base64.b64encode(buffered.getvalue()).decode()
except FileNotFoundError:
    logo_base64 = None

# Função para converter DataFrame para Excel em memória
@st.cache_data
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Resultados')
    processed_data = output.getvalue()
    return processed_data

# Função para lidar com erros de forma graciosa
def handle_error(message):
    st.error(message)
    st.stop()

# --- Layout da Página ---

# Cabeçalho com gradiente
st.markdown("""
    <div style='background: linear-gradient(to right, #62ac44, #53aacd, #8c54a4); padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); position: relative;'>
        <div style='position: absolute; top: 0; left: 0; right: 0; bottom: 0; border: 2px solid white; border-radius: 10px; pointer-events: none;'></div>
        <div style='display: flex; align-items: center; justify-content: space-between;'>
            <div style='display: flex; align-items: center;'>
                <div style='margin-right: 20px;'>
                    <img src='data:image/png;base64,{}' style='height: 60px; width: auto; object-fit: contain;'>
                </div>
                <div>
                    <h1 style='color: white; margin: 0; text-shadow: 1px 1px 2px rgba(0,0,0,0.2);'>ProNutrition Busca Inteligente</h1>
                    <p style='color: #ecf0f1; margin: 0;'>Encontre os melhores preços para seus suplementos</p>
                </div>
            </div>
        </div>
    </div>
""".format(logo_base64), unsafe_allow_html=True)

# Inicializa o scraper
try:
    scraper = SupplementScraper()
except Exception as e:
    handle_error(f"Erro ao inicializar o scraper: {str(e)}")

# Lista de lojas disponíveis
AVAILABLE_STORES = [
    "Amazon", "Growth Suplementos", "Integral Medica", "Netshoes",
    "Max Titanium", "Atlhetica Nutrition", "Probiótica", "Beleza na Web",
    "Época Cosméticos", "Onofre", "Droga Raia", "Panvel"
]

# Armazenar resultados no estado da sessão
if 'search_results' not in st.session_state:
    st.session_state.search_results = None
if 'last_query' not in st.session_state:
    st.session_state.last_query = ""
if 'selected_stores' not in st.session_state:
    st.session_state.selected_stores = AVAILABLE_STORES

# Formulário de busca
with st.form(key='search_form'):
    # Campo de busca principal
    st.markdown("""
        <div style='background: white; border-radius: 10px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 10px; max-width: 600px;'>
            <div style='margin-bottom: 10px; text-align: left;'>
                <h3 style='color: black; margin-bottom: 5px;'>🔍 O que você está procurando?</h3>
            </div>
    """, unsafe_allow_html=True)
    
    search_query = st.text_input(
        "",
        placeholder="Ex: Whey Protein, Creatina...",
        help="Digite o nome do produto que você está procurando"
    )
    
    # Botão de busca
    submit_button = st.form_submit_button(
        "🔍 Buscar Suplementos",
        use_container_width=True,
        type="primary",
        help="Clique para iniciar a busca"
    )
    
    # Container para o spinner
    spinner_container = st.empty()
    
    # Mensagem de busca
    if submit_button and search_query:
        with spinner_container:
            st.info(f"Buscando por '{search_query}'... Isso pode levar um minuto! ⏳")
    
    st.markdown("</div>", unsafe_allow_html=True)

# Dica útil
# Dica útil no final da página

# Filtros em colunas
col1, col2 = st.columns([1, 2])

with col1:
    # Filtros essenciais
    st.markdown("""
        <div style='background: white; border-radius: 10px; padding: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
            <h4 style='color: black; font-weight: bold; margin-bottom: 5px;'>💰 Faixa de Preço e Ordenação</h4>
    """, unsafe_allow_html=True)
    
    price_col1, price_col2 = st.columns(2)
    with price_col1:
        min_price = st.number_input(
            "Mínimo",
            min_value=0.0,
            value=0.0,
            step=10.0,
            format="%.2f",
            help="Preço mínimo em reais"
        )
    with price_col2:
        max_price = st.number_input(
            "Máximo",
            min_value=0.0,
            value=1000.0,
            step=10.0,
            format="%.2f",
            help="Preço máximo em reais"
        )
    
    sort_by = st.selectbox(
        "Ordenar por:",
        options=["Menor preço", "Maior preço", "Nome (A-Z)", "Loja"],
        index=0,
        help="Escolha como os resultados serão ordenados"
    )
    
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    # Filtros de lojas
    st.markdown("""
        <div style='background: white; border-radius: 10px; padding: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
            <h4 style='color: black; font-weight: bold; margin-bottom: 5px;'>🏪 Lojas</h4>
            <p style='color: #666; font-size: 0.9em; margin-bottom: 5px;'>Selecione as lojas onde deseja buscar</p>
    """, unsafe_allow_html=True)
    
    # Dividir lojas em duas colunas para melhor visualização
    store_col1, store_col2 = st.columns(2)
    
    with store_col1:
        st.markdown("**Lojas de Suplementos**")
        selected_stores = []
        for store in AVAILABLE_STORES[:6]:  # Primeiras 6 lojas
            if st.checkbox(store, value=True, key=f"store_{store}"):
                selected_stores.append(store)
    
    with store_col2:
        st.markdown("**Farmácias e Cosméticos**")
        for store in AVAILABLE_STORES[6:]:  # Últimas 6 lojas
            if st.checkbox(store, value=True, key=f"store_{store}"):
                selected_stores.append(store)
    
    st.session_state.selected_stores = selected_stores
    
    st.markdown("</div>", unsafe_allow_html=True)

# Quando o botão de busca for pressionado
if submit_button and search_query:
    st.session_state.last_query = search_query
    try:
        log_container = st.empty()
        log_container.info("Iniciando busca de suplementos...")

        results = scraper.search_supplements(search_query)
        
        # Aplicar filtros
        if results:
            # Filtrar por lojas selecionadas
            results = [r for r in results if r['store'] in st.session_state.selected_stores]
            
            # Filtrar por faixa de preço
            results = [r for r in results if min_price <= float(r['price']) <= max_price]
            
            # Ordenar resultados
            if sort_by == "Menor preço":
                results.sort(key=lambda x: float(x['price']) if float(x['price']) > 0 else float('inf'))
            elif sort_by == "Maior preço":
                results.sort(key=lambda x: float(x['price']) if float(x['price']) > 0 else float('-inf'), reverse=True)
            elif sort_by == "Nome (A-Z)":
                results.sort(key=lambda x: x['title'].lower())
            elif sort_by == "Loja":
                results.sort(key=lambda x: (x['store'], float(x['price']) if float(x['price']) > 0 else float('inf')))

        st.session_state.search_results = results

        log_container.success(f"Busca concluída! Encontrados {len(results)} produtos.")
        sleep(2)
        log_container.empty()

    except Exception as e:
        st.error(f"Ocorreu um erro durante a busca: {str(e)}")
        logging.error(f"Erro na busca por '{search_query}': {str(e)}", exc_info=True)
        st.session_state.search_results = None
        st.info("Tente digitar 'teste' na busca para ver resultados simulados.")
        st.stop()

# Exibir resultados se existirem no estado da sessão
if st.session_state.search_results is not None:
    results = st.session_state.search_results
    current_query = st.session_state.last_query

    if not results:
        st.warning(f"Não encontramos nenhum suplemento com o termo '{current_query}' dentro dos filtros selecionados. Tente ajustar os filtros ou use 'teste' para simulação.")
    else:
        # Cabeçalho dos resultados
        st.markdown(f"""
            <div style='background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;'>
                <h2 style='margin: 0;'>Resultados para '{current_query}'</h2>
                <p style='margin: 0; color: #666;'>{len(results)} produtos encontrados</p>
            </div>
        """, unsafe_allow_html=True)

        # Exportação para Excel
        df_export = pd.DataFrame(results)
        if not df_export.empty:
            df_export_final = df_export[['brand', 'price', 'link', 'query_date', 'store', 'title']].copy()
            df_export_final.rename(columns={
                'brand': 'Marca do produto',
                'price': 'Preco',
                'link': 'Link',
                'query_date': 'Data da consulta',
                'store': 'Loja',
                'title': 'Título Completo'
            }, inplace=True)
            excel_data = to_excel(df_export_final)
            st.download_button(
                label="📥 Exportar para Excel",
                data=excel_data,
                file_name=f"pronutrition_busca_{current_query.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Clique para baixar a tabela com os resultados da busca."
            )

        # Exibição dos resultados em cards
        cols = st.columns(3)
        for i, item in enumerate(results):
            with cols[i % 3]:
                st.markdown(f"""
                    <div class='product-card' style='margin-top: 20px;'>
                        <div style='text-align: center;'>
                            <img src='{item['image_url']}' style='max-width: 100%; height: auto; border-radius: 5px;'>
                        </div>
                        <h3 style='margin-top: 10px;'>{item['title'][:50]}{'...' if len(item['title']) > 50 else ''}</h3>
                        <div class='price-tag'>R$ {float(item['price']):.2f}</div>
                        <div style='margin: 10px 0;'>
                            <span class='store-badge'>{item['store']}</span>
                            <span class='brand-badge'>{item.get('brand', 'Sem marca')}</span>
                        </div>
                        <a href='{item['link']}' target='_blank' style='text-decoration: none;'>
                            <button style="width: 100%; padding: 10px; background-color: black; color: white; border: none; border-radius: 5px; cursor: pointer;">
                                Ver na loja 🛒
                            </button>
                        </a>
                    </div>
                """, unsafe_allow_html=True)
st.info("💡 Dica: Digite 'teste' para ver resultados simulados e testar o app!")

# Rodapé
st.markdown("--- ")
st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>© 2025 ProNutrition Busca Inteligente</p>
    </div>
""", unsafe_allow_html=True)