from datetime import date, timedelta

import pandas as pd
import requests

URL_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

# O IPCA é calculado pelo IBGE e disponibilizado no SGS do Banco Central.
SERIES = {
    "IPCA": {"codigo_sgs": 433, "unidade": "% a.m.", "fonte": "BCB-SGS"},
    "SELIC_META": {"codigo_sgs": 432, "unidade": "% a.a.", "fonte": "BCB-SGS"},
}


class ErroDeColeta(Exception):
    """Erro com mensagem compreensível ao buscar ou tratar dados."""


def buscar_dados_brutos(codigo_sgs, data_inicial, data_final):
    """Consulta a API do Banco Central e devolve a lista bruta (JSON)."""
    url = URL_BASE.format(codigo=codigo_sgs)
    parametros = {
        "formato": "json",
        "dataInicial": data_inicial.strftime("%d/%m/%Y"),
        "dataFinal": data_final.strftime("%d/%m/%Y"),
    }

    try:
        resposta = requests.get(url, params=parametros, timeout=30)
        resposta.raise_for_status()
        dados = resposta.json()
    except requests.exceptions.RequestException as erro:
        raise ErroDeColeta(f"Falha ao consultar a série {codigo_sgs}: {erro}") from erro
    except ValueError as erro:
        raise ErroDeColeta(f"A série {codigo_sgs} não retornou um JSON válido.") from erro

    if not dados:
        raise ErroDeColeta(f"A série {codigo_sgs} voltou vazia para o período pedido.")

    return dados


def tratar_dados(dados, nome):
    """Converte a lista bruta em uma tabela limpa, no formato da tabela do banco."""
    info = SERIES[nome]
    df = pd.DataFrame(dados)

    if not {"data", "valor"}.issubset(df.columns):
        raise ErroDeColeta(f"A série {nome} veio sem os campos 'data' e 'valor'.")

    # Texto -> data e texto -> número. errors="coerce" troca o que não der para converter por vazio (NaT/NaN)
    df["data_referencia"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    # Validação: remove linhas com data ou valor inválido, avisando quantas foram
    invalidas = df[["data_referencia", "valor"]].isna().any(axis=1).sum()
    if invalidas > 0:
        print(f"Aviso [{nome}]: {invalidas} linha(s) inválida(s) removida(s).")
        df = df.dropna(subset=["data_referencia", "valor"])

    if df.empty:
        raise ErroDeColeta(f"A série {nome} ficou vazia depois da validação.")

    # Evita duplicar a mesma data e organiza do mais antigo ao mais recente
    df = df.drop_duplicates(subset="data_referencia").sort_values("data_referencia")

    # Colunas que combinam com a tabela dbo.indicadores
    df["codigo"] = nome
    df["unidade"] = info["unidade"]
    df["fonte"] = info["fonte"]

    colunas = ["codigo", "data_referencia", "valor", "unidade", "fonte"]
    return df[colunas].reset_index(drop=True)


if __name__ == "__main__":
    # Este bloco só roda quando você executa o arquivo diretamente (teste)
    hoje = date.today()
    inicio = hoje - timedelta(days=365)

    for nome, info in SERIES.items():
        print("=" * 60)
        print(nome)
        try:
            bruto = buscar_dados_brutos(info["codigo_sgs"], inicio, hoje)
            tabela = tratar_dados(bruto, nome)
        except ErroDeColeta as erro:
            print(f"Erro: {erro}")
            continue

        print("Linhas:", len(tabela))
        print(tabela.head(3))
        print(tabela.tail(3))
        print(tabela.dtypes)

        fins_de_semana = (tabela["data_referencia"].dt.dayofweek >= 5).sum()
        print("Registros em sábado/domingo:", fins_de_semana)