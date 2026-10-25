import pandas as pd
import plotly.express as px
import streamlit as st

import analysis
import database

st.set_page_config(
    page_title="Market Insights BR",
    page_icon="📈",
    layout="wide",
)

# Estilo: cards em azul com faixa ciano no topo
ESTILO = """
<style>
[data-testid="stMetric"] {
    background-color: #12233D;
    border: 1px solid #1E3A5F;
    border-top: 3px solid #22D3EE;
    border-radius: 12px;
    padding: 14px 18px;
}
[data-testid="stSidebar"] {
    border-right: 1px solid #1E3A5F;
}
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600)
def carregar_dados():
    """Lê o banco uma vez e guarda o resultado por 10 minutos."""
    return database.ler_indicadores()


def formatar(valor, casas=2):
    """Número no padrão brasileiro: vírgula como separador decimal."""
    return f"{valor:.{casas}f}".replace(".", ",")


def formatar_delta(valor):
    return f"{valor:+.2f}".replace(".", ",") + " p.p."


def grafico_linha(df, titulo, unidade, cor):
    grafico = px.line(
        df,
        x="data_referencia",
        y="valor",
        title=titulo,
        labels={"data_referencia": "Data", "valor": unidade},
        markers=len(df) <= 80,
    )
    grafico.update_traces(line_color=cor)
    grafico.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return grafico


def mostrar_comparativo(tabela):
    st.dataframe(
        tabela,
        hide_index=True,
        width="stretch",
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Valor": st.column_config.NumberColumn("Valor", format="%.2f"),
            "Variação até o último dado (p.p.)": st.column_config.NumberColumn(format="%.2f"),
        },
    )


# ---------------------------------------------------------------------------
# Menu lateral e cabeçalho
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📈 Market Insights BR")
    pagina = st.radio(
        "Navegação",
        ["Início", "Indicadores", "Análises", "Sobre"],
    )

st.title("Market Insights BR")
st.caption("Dados que geram melhores decisões")

# ---------------------------------------------------------------------------
# Leitura do banco, com tratamento de erro e de banco vazio
# ---------------------------------------------------------------------------
try:
    dados = carregar_dados()
except database.ErroDeBanco as erro:
    st.error(f"{erro} Rode `python database.py` no terminal para ver o detalhe técnico.")
    st.stop()

if dados.empty:
    st.info(
        "Ainda não há dados no banco. Rode `python atualizar_dados.py` "
        "no terminal para carregar os indicadores."
    )
    st.stop()

ipca = dados[dados["codigo"] == "IPCA"]
selic = dados[dados["codigo"] == "SELIC_META"]

# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
if pagina == "Início":
    col1, col2, col3 = st.columns(3)

    # Card 1: IPCA do último mês, comparado ao mês anterior
    if len(ipca) >= 2:
        atual, anterior = ipca.iloc[-1], ipca.iloc[-2]
        col1.metric(
            f"IPCA, variação mensal ({atual['data_referencia']:%m/%Y})",
            f"{formatar(atual['valor'])}% a.m.",
            formatar_delta(atual["valor"] - anterior["valor"]),
            delta_color="off",
            help="A seta compara com o mês anterior, em pontos percentuais (p.p.).",
        )
    else:
        col1.info("Dados de IPCA insuficientes no banco.")

    # Card 2: meta Selic atual, comparada a 12 meses antes
    if not selic.empty:
        ultima = selic.iloc[-1]
        limite = ultima["data_referencia"] - pd.DateOffset(years=1)
        base = selic[selic["data_referencia"] <= limite]
        delta = formatar_delta(ultima["valor"] - base.iloc[-1]["valor"]) if not base.empty else None
        col2.metric(
            f"Meta Selic ({ultima['data_referencia']:%d/%m/%Y})",
            f"{formatar(ultima['valor'])}% a.a.",
            delta,
            delta_color="off",
            help="A seta compara com o valor de 12 meses antes, em pontos percentuais (p.p.).",
        )
    else:
        col2.info("Dados da Selic insuficientes no banco.")

    # Card 3: quando entraram os dados mais recentes no banco
    ultima_coleta = dados["coletado_em"].max()
    col3.metric(
        "Última coleta com novos dados",
        f"{ultima_coleta:%d/%m/%Y %H:%M}",
        help="Momento em que o Python gravou no banco o registro mais recente.",
    )

    st.caption(
        "Fonte: Banco Central do Brasil (SGS), séries 433 (IPCA) e 432 (meta Selic). "
        "Dados lidos do SQL Server."
    )

    # Gráficos
    g1, g2 = st.columns(2)
    g1.plotly_chart(
        grafico_linha(ipca, "IPCA, variação mensal (% a.m.)", "% a.m.", "#22D3EE"),
        width="stretch",
    )
    g2.plotly_chart(
        grafico_linha(selic, "Meta Selic (% a.a.)", "% a.a.", "#A78BFA"),
        width="stretch",
    )

    # Tabela: 5 registros mais recentes de cada indicador
    st.subheader("Últimos dados disponíveis")
    ultimos = (
        dados.sort_values("data_referencia", ascending=False)
        .groupby("codigo")
        .head(5)
        .sort_values(["codigo", "data_referencia"], ascending=[True, False])
        [["codigo", "data_referencia", "valor", "unidade", "fonte"]]
    )
    st.dataframe(
        ultimos,
        hide_index=True,
        width="stretch",
        column_config={
            "codigo": "Indicador",
            "data_referencia": st.column_config.DateColumn("Data de referência", format="DD/MM/YYYY"),
            "valor": st.column_config.NumberColumn("Valor", format="%.2f"),
            "unidade": "Unidade",
            "fonte": "Fonte",
        },
    )

elif pagina == "Indicadores":
    st.subheader("Indicadores")

    opcoes = {
        "IPCA, variação mensal": "IPCA",
        "Meta Selic": "SELIC_META",
    }
    cores = {"IPCA": "#22D3EE", "SELIC_META": "#A78BFA"}

    escolhido = st.selectbox("Indicador", list(opcoes.keys()))
    codigo = opcoes[escolhido]
    serie = dados[dados["codigo"] == codigo]

    if serie.empty:
        st.info("Não há dados deste indicador no banco.")
        st.stop()

    unidade = serie["unidade"].iloc[0]
    data_min = serie["data_referencia"].min().date()
    data_max = serie["data_referencia"].max().date()
    ultima_data = serie["data_referencia"].max()

    periodo = st.radio(
        "Período",
        ["Últimos 12 meses", "Últimos 3 anos", "Todo o período", "Personalizado"],
        horizontal=True,
    )

    if periodo == "Últimos 12 meses":
        filtrado = serie[serie["data_referencia"] > ultima_data - pd.DateOffset(months=12)]
    elif periodo == "Últimos 3 anos":
        filtrado = serie[serie["data_referencia"] > ultima_data - pd.DateOffset(years=3)]
    elif periodo == "Todo o período":
        filtrado = serie
    else:
        escolha = st.date_input(
            "Escolha a data inicial e a data final",
            value=(data_min, data_max),
            min_value=data_min,
            max_value=data_max,
            format="DD/MM/YYYY",
        )
        if len(escolha) != 2:
            st.info("Selecione também a data final para aplicar o filtro.")
            st.stop()
        inicio, fim = escolha
        filtrado = serie[
            (serie["data_referencia"] >= pd.Timestamp(inicio))
            & (serie["data_referencia"] <= pd.Timestamp(fim))
        ]

    if filtrado.empty:
        st.info("Não há dados no período escolhido.")
        st.stop()

    # Estatísticas do período filtrado
    linha_min = filtrado.loc[filtrado["valor"].idxmin()]
    linha_max = filtrado.loc[filtrado["valor"].idxmax()]
    media = filtrado["valor"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros no período", f"{len(filtrado)}")
    c2.metric(
        "Mínimo",
        f"{formatar(linha_min['valor'])} {unidade}",
        help=f"Ocorreu em {linha_min['data_referencia']:%d/%m/%Y}.",
    )
    c3.metric(
        "Máximo",
        f"{formatar(linha_max['valor'])} {unidade}",
        help=f"Ocorreu em {linha_max['data_referencia']:%d/%m/%Y}.",
    )
    c4.metric(
        "Média",
        f"{formatar(media)} {unidade}",
        help="Média simples de todos os registros do período. Na Selic, cada dia corrido conta uma vez.",
    )

    grafico = grafico_linha(filtrado, f"{escolhido} ({unidade})", unidade, cores[codigo])
    grafico.add_hline(
        y=media,
        line_dash="dash",
        line_color="#FB923C",
        annotation_text="Média do período",
        annotation_position="top left",
    )
    st.plotly_chart(grafico, width="stretch")

    st.subheader("Dados do período")
    st.dataframe(
        filtrado.sort_values("data_referencia", ascending=False)[
            ["data_referencia", "valor", "unidade", "fonte"]
        ],
        hide_index=True,
        width="stretch",
        height=400,
        column_config={
            "data_referencia": st.column_config.DateColumn("Data de referência", format="DD/MM/YYYY"),
            "valor": st.column_config.NumberColumn("Valor", format="%.2f"),
            "unidade": "Unidade",
            "fonte": "Fonte",
        },
    )

elif pagina == "Análises":
    st.subheader("Análises")

    # Painel de insights, escritos a partir dos dados do banco
    st.markdown("#### Principais insights")
    insights = analysis.gerar_insights(ipca, selic)
    if insights:
        with st.container(border=True):
            for texto in insights:
                st.markdown(f"- {texto}")
        st.caption(
            "Frases geradas automaticamente a partir dos dados do banco. "
            "Elas descrevem o que os números mostram e não indicam causa."
        )
    else:
        st.info("Ainda não há dados suficientes para gerar insights.")

    # IPCA acumulado em 12 meses
    st.markdown("#### IPCA acumulado em 12 meses")
    try:
        ipca_acum = analysis.ipca_acumulado_12_meses(ipca).dropna(subset=["acumulado_12m"])
    except ValueError as erro:
        st.warning(str(erro))
        ipca_acum = pd.DataFrame()

    if ipca_acum.empty:
        st.info("Dados insuficientes para calcular o acumulado em 12 meses.")
    else:
        base_acum = ipca_acum[["data_referencia", "acumulado_12m"]].rename(
            columns={"acumulado_12m": "valor"}
        )
        st.plotly_chart(
            grafico_linha(base_acum, "IPCA acumulado em 12 meses (%)", "%", "#34D399"),
            width="stretch",
        )
        st.caption(
            "Calculado compondo as 12 últimas variações mensais. Pode diferir em centésimos "
            "do número oficial por causa do arredondamento."
        )

    # Comparativos entre períodos
    st.markdown("#### Comparativo entre períodos")
    aba_selic, aba_ipca = st.tabs(["Meta Selic (% a.a.)", "IPCA mensal (% a.m.)"])
    with aba_selic:
        mostrar_comparativo(analysis.comparativo(selic, (1, 6, 12)))
    with aba_ipca:
        mostrar_comparativo(analysis.comparativo(ipca, (1, 12)))
    st.caption("As diferenças são em pontos percentuais (p.p.), sempre do valor antigo até o último dado.")

    with st.expander("Como ler as unidades"):
        st.markdown(
            "- **% a.m.** é percentual ao mês (o IPCA mensal). **% a.a.** é percentual ao ano (a meta Selic).\n"
            "- **p.p.** (pontos percentuais) é a diferença entre dois percentuais: de 15,00% para 13,75% "
            "a queda é de 1,25 p.p.\n"
            "- IPCA mensal e Selic estão em unidades diferentes. Para compará-los, usamos o IPCA "
            "**acumulado em 12 meses**, que está na mesma base anual."
        )

else:
    st.subheader("Sobre o projeto")

    st.markdown(
        """
**Market Insights BR** é um projeto de portfólio que reúne indicadores econômicos brasileiros
em um dashboard. Ele mostra o caminho completo dos dados: coleta em fonte oficial, tratamento,
armazenamento em banco de dados, análise e visualização.

#### Como os dados percorrem o projeto

1. **Python + Requests** consultam a API do Banco Central do Brasil.
2. **Pandas** converte tipos, valida e organiza os dados.
3. **SQL Server** guarda o histórico, sem duplicar registros.
4. **Streamlit** lê o banco (e não a API) e **Plotly** desenha os gráficos.
5. **analysis.py** calcula variações, acumulados e escreve os insights.

A atualização dos dados é um script separado (`atualizar_dados.py`). Mexer nos filtros do
dashboard nunca dispara uma nova consulta à API.
"""
    )

    st.markdown("#### Tecnologias")
    st.markdown(
        """
| Tecnologia | Uso no projeto |
|---|---|
| Python | Linguagem principal |
| Requests | Consulta à API do Banco Central |
| Pandas | Tratamento, validação e cálculos |
| SQL Server + pyodbc | Armazenamento e gravação dos dados |
| SQLAlchemy | Leitura do banco para o Pandas |
| Streamlit | Interface web |
| Plotly | Gráficos interativos |
"""
    )

    st.markdown("#### Fontes de dados")
    st.markdown(
        """
Dados públicos do **Banco Central do Brasil**, pelo Sistema Gerenciador de Séries Temporais (SGS):

- **Série 433:** IPCA, variação mensal (% ao mês). O IPCA é o índice oficial de inflação,
  calculado pelo IBGE.
- **Série 432:** meta Selic definida pelo Copom (% ao ano), com um valor por dia corrido.
"""
    )

    st.markdown("#### Cobertura dos dados no banco")
    cobertura = (
        dados.groupby("codigo")
        .agg(
            registros=("valor", "size"),
            primeira=("data_referencia", "min"),
            ultima=("data_referencia", "max"),
        )
        .reset_index()
    )
    st.dataframe(
        cobertura,
        hide_index=True,
        width="stretch",
        column_config={
            "codigo": "Indicador",
            "registros": "Registros",
            "primeira": st.column_config.DateColumn("Primeira data", format="DD/MM/YYYY"),
            "ultima": st.column_config.DateColumn("Última data", format="DD/MM/YYYY"),
        },
    )

    st.markdown("#### Limitações")
    st.markdown(
        """
- **Atualização manual:** os dados só mudam quando o script `atualizar_dados.py` é executado.
  O dashboard guarda a leitura do banco por 10 minutos.
- **Só entram datas novas:** se o Banco Central revisar um valor antigo, o banco não é corrigido.
- **IPCA acumulado em 12 meses é calculado aqui**, compondo as variações mensais. Pode diferir
  em centésimos do número oficial por causa de arredondamentos.
- **A Selic mostrada é a meta definida pelo Copom**, e não a taxa efetivamente praticada no mercado.
- **Unidades diferentes:** IPCA mensal (% a.m.) e Selic (% a.a.) não são comparáveis diretamente.
  Por isso a comparação usa o IPCA acumulado em 12 meses.
- **Insights são descritivos:** eles mostram o que os números dizem. Não indicam causa nem
  fazem previsão, e correlação entre indicadores não significa causalidade.
- **Histórico limitado:** o banco guarda 5 anos de dados, e não toda a série histórica.
"""
    )

    st.markdown("#### Documentação técnica")
    st.markdown(
        """
| Arquivo | Função |
|---|---|
| `app.py` | Interface Streamlit: páginas, filtros e gráficos |
| `database.py` | Conexão e operações com o SQL Server |
| `data_ingestion.py` | Coleta na API e tratamento com Pandas |
| `atualizar_dados.py` | Atualiza o banco (rodar no terminal) |
| `analysis.py` | Cálculos e geração dos insights |

Para atualizar os dados: `python atualizar_dados.py`. Para abrir o dashboard:
`python -m streamlit run app.py`.
"""
    )