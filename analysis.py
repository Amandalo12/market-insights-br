import numpy as np
import pandas as pd


def _fmt(valor, casas=2):
    """Número no padrão brasileiro (vírgula decimal)."""
    return f"{valor:.{casas}f}".replace(".", ",")

def _plural(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"

def _comparacao(dif):
    """Frase curta para a diferença entre dois valores, em p.p."""
    if dif > 0:
        return f"{_fmt(abs(dif))} p.p. acima do"
    if dif < 0:
        return f"{_fmt(abs(dif))} p.p. abaixo do"
    return "igual ao"


def valor_em_ou_antes(serie, data_alvo):
    """Último registro com data menor ou igual à data pedida (ou None)."""
    serie = serie.sort_values("data_referencia")
    candidatos = serie[serie["data_referencia"] <= data_alvo]
    if candidatos.empty:
        return None
    return candidatos.iloc[-1]


def ipca_acumulado_12_meses(ipca):
    """Acrescenta a coluna 'acumulado_12m' (em %) compondo 12 variações mensais."""
    ipca = ipca.sort_values("data_referencia").reset_index(drop=True).copy()

    # Só acumula se não faltar nenhum mês no meio da série
    indice_mes = ipca["data_referencia"].dt.year * 12 + ipca["data_referencia"].dt.month
    if not indice_mes.diff().dropna().eq(1).all():
        raise ValueError(
            "A série de IPCA tem meses faltando, então não dá para acumular 12 meses com segurança."
        )

    fator = 1 + ipca["valor"] / 100
    ipca["acumulado_12m"] = (fator.rolling(12).apply(np.prod, raw=True) - 1) * 100
    return ipca


def comparativo(serie, meses_atras=(1, 6, 12)):
    """Compara o último valor com o de N meses antes. Devolve um DataFrame."""
    serie = serie.sort_values("data_referencia")
    atual = serie.iloc[-1]

    linhas = [
        {
            "Referência": "Último dado",
            "Data": atual["data_referencia"],
            "Valor": atual["valor"],
            "Variação até o último dado (p.p.)": None,
        }
    ]
    for n in meses_atras:
        base = valor_em_ou_antes(serie, atual["data_referencia"] - pd.DateOffset(months=n))
        if base is None:
            continue
        linhas.append(
            {
                "Referência": f"{n} {'mês' if n == 1 else 'meses'} antes",
                "Data": base["data_referencia"],
                "Valor": base["valor"],
                "Variação até o último dado (p.p.)": atual["valor"] - base["valor"],
            }
        )
    return pd.DataFrame(linhas)


def mudancas_da_meta(selic, meses=12):
    """Conta quantas altas e quedas a meta Selic teve nos últimos N meses."""
    selic = selic.sort_values("data_referencia").copy()
    selic["dif"] = selic["valor"].diff()
    limite = selic["data_referencia"].max() - pd.DateOffset(months=meses)
    recorte = selic[selic["data_referencia"] > limite]
    altas = int((recorte["dif"] > 0).sum())
    quedas = int((recorte["dif"] < 0).sum())
    return altas, quedas


def gerar_insights(ipca, selic):
    """Escreve frases descritivas a partir dos dados. Lista vazia se não houver dados."""
    insights = []
    acumulado_atual = None
    selic_atual = None

    # IPCA: último mês e acumulado em 12 meses
    if len(ipca) >= 2:
        ipca = ipca.sort_values("data_referencia")
        atual, anterior = ipca.iloc[-1], ipca.iloc[-2]
        dif = atual["valor"] - anterior["valor"]
        insights.append(
            f"O IPCA de {atual['data_referencia']:%m/%Y} foi de {_fmt(atual['valor'])}% a.m., "
            f"{_comparacao(dif)} mês anterior ({_fmt(anterior['valor'])}% a.m.)."
        )

        try:
            acum = ipca_acumulado_12_meses(ipca).dropna(subset=["acumulado_12m"])
        except ValueError:
            acum = ipca.iloc[0:0]
        if not acum.empty:
            ultimo = acum.iloc[-1]
            acumulado_atual = ultimo["acumulado_12m"]
            insights.append(
                f"O IPCA acumulado em 12 meses até {ultimo['data_referencia']:%m/%Y} é de "
                f"{_fmt(acumulado_atual)}% (calculado a partir das variações mensais)."
            )

    # Selic: valor atual, comparação com 12 meses antes e mudanças da meta
    if not selic.empty:
        selic = selic.sort_values("data_referencia")
        atual = selic.iloc[-1]
        selic_atual = atual["valor"]
        base = valor_em_ou_antes(selic, atual["data_referencia"] - pd.DateOffset(years=1))
        if base is not None:
            dif = atual["valor"] - base["valor"]
            insights.append(
                f"A meta Selic está em {_fmt(atual['valor'])}% a.a. ({atual['data_referencia']:%d/%m/%Y}), "
                f"{_comparacao(dif)} valor de 12 meses antes ({_fmt(base['valor'])}% a.a.)."
            )
        altas, quedas = mudancas_da_meta(selic, 12)
        insights.append(
            f"Nos últimos 12 meses, a meta Selic teve {_plural(quedas, 'redução', 'reduções')} "
            f"e {_plural(altas, 'aumento', 'aumentos')}."
        )

    # Comparação entre as duas séries, em unidades compatíveis (% a.a.)
    if acumulado_atual is not None and selic_atual is not None:
        dif = selic_atual - acumulado_atual
        posicao = "acima" if dif >= 0 else "abaixo"
        insights.append(
            f"A meta Selic atual ({_fmt(selic_atual)}% a.a.) está {_fmt(abs(dif))} p.p. {posicao} do IPCA "
            f"acumulado em 12 meses ({_fmt(acumulado_atual)}%). É uma comparação simples entre o juro de hoje "
            "e a inflação passada, não uma projeção."
        )

    return insights