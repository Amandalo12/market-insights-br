import pytest

import data_ingestion


def test_tratar_dados_converte_texto_em_data_e_numero():
    bruto = [
        {"data": "01/10/2025", "valor": "0.09"},
        {"data": "01/11/2025", "valor": "-0.32"},
    ]
    tabela = data_ingestion.tratar_dados(bruto, "IPCA")

    assert list(tabela.columns) == ["codigo", "data_referencia", "valor", "unidade", "fonte"]
    assert str(tabela["data_referencia"].dtype).startswith("datetime64")
    assert tabela["valor"].tolist() == [0.09, -0.32]
    assert tabela["codigo"].iloc[0] == "IPCA"
    assert tabela["unidade"].iloc[0] == "% a.m."


def test_tratar_dados_remove_linhas_invalidas():
    bruto = [
        {"data": "01/10/2025", "valor": "0.09"},
        {"data": "31/02/2025", "valor": "1.00"},  # data que não existe
        {"data": "01/12/2025", "valor": "abc"},  # valor que não é número
    ]
    tabela = data_ingestion.tratar_dados(bruto, "IPCA")
    assert len(tabela) == 1


def test_tratar_dados_remove_datas_repetidas():
    bruto = [
        {"data": "01/10/2025", "valor": "0.09"},
        {"data": "01/10/2025", "valor": "0.09"},
    ]
    assert len(data_ingestion.tratar_dados(bruto, "IPCA")) == 1


def test_tratar_dados_ordena_da_data_mais_antiga_para_a_mais_recente():
    bruto = [
        {"data": "01/11/2025", "valor": "0.18"},
        {"data": "01/10/2025", "valor": "0.09"},
    ]
    tabela = data_ingestion.tratar_dados(bruto, "IPCA")
    assert tabela["valor"].tolist() == [0.09, 0.18]


def test_tratar_dados_exige_os_campos_data_e_valor():
    with pytest.raises(data_ingestion.ErroDeColeta):
        data_ingestion.tratar_dados([{"x": 1}], "IPCA")


def test_tratar_dados_erro_quando_tudo_e_invalido():
    with pytest.raises(data_ingestion.ErroDeColeta):
        data_ingestion.tratar_dados([{"data": "xx", "valor": "yy"}], "IPCA")