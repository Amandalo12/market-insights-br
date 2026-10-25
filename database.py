from decimal import Decimal
from urllib.parse import quote_plus

import pandas as pd
import pyodbc
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

DRIVER = "ODBC Driver 18 for SQL Server"
SERVIDOR = "localhost"
BANCO = "MarketInsightsBR"


class ErroDeBanco(Exception):
    """Erro com mensagem compreensível ao falar com o SQL Server."""


def montar_texto_conexao():
    """Monta o texto de conexão (autenticação do Windows, sem senha)."""
    return (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVIDOR};"
        f"DATABASE={BANCO};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )


def conectar():
    """Abre uma conexão pyodbc (usada para gravar)."""
    try:
        return pyodbc.connect(montar_texto_conexao(), timeout=10)
    except pyodbc.Error as erro:
        raise ErroDeBanco(
            "Não foi possível conectar ao SQL Server. Verifique se o serviço está "
            f"em execução, se o banco '{BANCO}' existe e se o driver "
            f"'{DRIVER}' está instalado."
        ) from erro


def criar_engine():
    """Cria um 'engine' do SQLAlchemy (usado para ler com o Pandas)."""
    url = "mssql+pyodbc:///?odbc_connect=" + quote_plus(montar_texto_conexao())
    return create_engine(url)


def testar_conexao():
    """Devolve o banco, o usuário conectado e o total de registros da tabela."""
    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute(
            "SELECT DB_NAME(), SUSER_SNAME(), (SELECT COUNT(*) FROM dbo.indicadores)"
        )
        banco, usuario, total = cursor.fetchone()
        return banco, usuario, total
    except pyodbc.Error as erro:
        raise ErroDeBanco("A conexão abriu, mas a consulta de teste falhou.") from erro
    finally:
        conexao.close()


def gravar_indicadores(tabela):
    """Grava no banco só os registros que ainda não existem.

    Espera uma tabela do Pandas com UM único indicador (uma série).
    Devolve (quantos_novos, quantos_ja_existiam).
    """
    if tabela.empty:
        return 0, 0

    codigo = tabela["codigo"].iloc[0]

    conexao = conectar()
    try:
        cursor = conexao.cursor()

        cursor.execute(
            "SELECT data_referencia FROM dbo.indicadores WHERE codigo = ?",
            codigo,
        )
        existentes = {linha[0] for linha in cursor.fetchall()}

        datas = tabela["data_referencia"].dt.date
        novas = tabela[~datas.isin(existentes)]

        linhas = [
            (
                linha.codigo,
                linha.data_referencia.date(),
                Decimal(str(linha.valor)),
                linha.unidade,
                linha.fonte,
            )
            for linha in novas.itertuples(index=False)
        ]

        if linhas:
            cursor.executemany(
                "INSERT INTO dbo.indicadores "
                "(codigo, data_referencia, valor, unidade, fonte) "
                "VALUES (?, ?, ?, ?, ?)",
                linhas,
            )
        conexao.commit()
        return len(linhas), len(tabela) - len(linhas)

    except pyodbc.Error as erro:
        conexao.rollback()
        raise ErroDeBanco(
            f"Falha ao gravar a série {codigo}. Nenhum registro dessa série foi salvo."
        ) from erro
    finally:
        conexao.close()


def resumo_por_indicador():
    """Devolve, por indicador: total, primeira data, última data e última coleta."""
    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute(
            "SELECT codigo, COUNT(*), MIN(data_referencia), "
            "MAX(data_referencia), MAX(coletado_em) "
            "FROM dbo.indicadores GROUP BY codigo ORDER BY codigo"
        )
        return cursor.fetchall()
    except pyodbc.Error as erro:
        raise ErroDeBanco("Não foi possível ler o resumo dos indicadores.") from erro
    finally:
        conexao.close()


def ler_indicadores(codigo=None):
    """Lê os indicadores do banco e devolve um DataFrame do Pandas.

    Se 'codigo' for informado, devolve só aquele indicador.
    """
    sql = (
        "SELECT codigo, data_referencia, valor, unidade, fonte, coletado_em "
        "FROM dbo.indicadores"
    )
    parametros = {}
    if codigo is not None:
        sql += " WHERE codigo = :codigo"
        parametros["codigo"] = codigo
    sql += " ORDER BY codigo, data_referencia"

    engine = criar_engine()
    try:
        with engine.connect() as conexao:
            tabela = pd.read_sql(text(sql), conexao, params=parametros or None)
    except SQLAlchemyError as erro:
        raise ErroDeBanco("Não foi possível ler os indicadores do SQL Server.") from erro
    finally:
        engine.dispose()

    # O banco devolve DECIMAL e DATE: convertemos para os tipos que o Pandas usa
    tabela["data_referencia"] = pd.to_datetime(tabela["data_referencia"])
    tabela["valor"] = tabela["valor"].astype(float)
    return tabela


if __name__ == "__main__":
    try:
        banco, usuario, total = testar_conexao()
    except ErroDeBanco as erro:
        print("Erro:", erro)
        print("Detalhe técnico:", erro.__cause__)
    else:
        print("Conexão OK")
        print("Banco:", banco)
        print("Usuário:", usuario)
        print("Registros em dbo.indicadores:", total)