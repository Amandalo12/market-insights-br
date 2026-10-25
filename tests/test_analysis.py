import pandas as pd
import pytest

import analysis


def criar_serie_mensal(valores, inicio="2025-01-01"):
    """Cria uma série mensal (dia 1 de cada mês) no formato que o projeto usa."""
    datas = pd.date_range(inicio, periods=len(valores), freq="MS")
    return pd.DataFrame({"data_referencia": datas, "valor": valores})


def test_ipca_acumulado_compoe_as_variacoes():
    # 12 meses de 1% ao mês: (1,01 ** 12 - 1) * 100 = 12,6825...
    ipca = criar_serie_mensal([1.0] * 12)
    resultado = analysis.ipca_acumulado_12_meses(ipca)
    assert resultado["acumulado_12m"].iloc[-1] == pytest.approx(12.682503, abs=1e-5)


def test_ipca_acumulado_so_aparece_com_12_meses_de_historico():
    ipca = criar_serie_mensal([0.5] * 13)
    resultado = analysis.ipca_acumulado_12_meses(ipca)
    assert resultado["acumulado_12m"].iloc[:11].isna().all()
    assert resultado["acumulado_12m"].iloc[11:].notna().all()


def test_ipca_acumulado_recusa_serie_com_mes_faltando():
    datas = pd.to_datetime(["2025-01-01", "2025-02-01", "2025-04-01"])
    ipca = pd.DataFrame({"data_referencia": datas, "valor": [0.1, 0.2, 0.3]})
    with pytest.raises(ValueError, match="meses faltando"):
        analysis.ipca_acumulado_12_meses(ipca)


def test_valor_em_ou_antes_usa_o_registro_anterior_mais_proximo():
    serie = pd.DataFrame(
        {
            "data_referencia": pd.to_datetime(["2025-01-01", "2025-01-10"]),
            "valor": [10.0, 20.0],
        }
    )
    registro = analysis.valor_em_ou_antes(serie, pd.Timestamp("2025-01-05"))
    assert registro["valor"] == 10.0
    assert analysis.valor_em_ou_antes(serie, pd.Timestamp("2024-12-01")) is None


def test_comparativo_calcula_variacao_em_pontos_percentuais():
    serie = criar_serie_mensal(list(range(13)))  # valores de 0 a 12
    tabela = analysis.comparativo(serie, (1, 12))

    assert tabela["Referência"].tolist() == ["Último dado", "1 mês antes", "12 meses antes"]
    variacoes = tabela["Variação até o último dado (p.p.)"].tolist()
    assert variacoes[1] == pytest.approx(1.0)
    assert variacoes[2] == pytest.approx(12.0)


def test_mudancas_da_meta_conta_altas_e_quedas():
    datas = pd.date_range("2026-01-01", periods=6, freq="D")
    selic = pd.DataFrame(
        {"data_referencia": datas, "valor": [15.0, 15.0, 14.5, 14.75, 14.25, 14.25]}
    )
    altas, quedas = analysis.mudancas_da_meta(selic, 12)
    assert (altas, quedas) == (1, 2)


def test_insights_descrevem_ipca_estavel():
    ipca = criar_serie_mensal([1.0] * 13)
    selic = pd.DataFrame(columns=["data_referencia", "valor"])
    texto = " ".join(analysis.gerar_insights(ipca, selic))
    assert "igual ao mês anterior" in texto
    assert "12,68%" in texto


def test_insights_sem_dados_devolve_lista_vazia():
    vazio = pd.DataFrame(columns=["data_referencia", "valor"])
    assert analysis.gerar_insights(vazio, vazio) == []