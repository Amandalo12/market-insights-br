from datetime import date, timedelta

import data_ingestion
import database

# Quantos anos de histórico buscar. Para séries diárias (Selic), o Banco Central
# aceita no máximo 10 anos por consulta. Com 5 ficamos bem abaixo do limite.
ANOS_DE_HISTORICO = 5


def atualizar():
    hoje = date.today()
    inicio = hoje - timedelta(days=365 * ANOS_DE_HISTORICO)
    falhas = 0

    for nome, info in data_ingestion.SERIES.items():
        print(f"\n{nome}: buscando de {inicio:%d/%m/%Y} a {hoje:%d/%m/%Y}...")
        try:
            bruto = data_ingestion.buscar_dados_brutos(info["codigo_sgs"], inicio, hoje)
            tabela = data_ingestion.tratar_dados(bruto, nome)
            novos, existentes = database.gravar_indicadores(tabela)
        except (data_ingestion.ErroDeColeta, database.ErroDeBanco) as erro:
            print(f"  Erro: {erro}")
            falhas += 1
            continue

        print(
            f"  Recebidos: {len(tabela)} | "
            f"Novos gravados: {novos} | Já existiam: {existentes}"
        )

    print("\nResumo do banco:")
    try:
        for codigo, total, primeira, ultima, coleta in database.resumo_por_indicador():
            print(f"  {codigo}: {total} registros | {primeira} a {ultima} | última coleta: {coleta}")
    except database.ErroDeBanco as erro:
        print(f"  Erro: {erro}")
        falhas += 1

    return falhas == 0


if __name__ == "__main__":
    sucesso = atualizar()
    if sucesso:
        print("\nAtualização concluída com sucesso.")
    else:
        print("\nAtualização concluída com falhas. Veja as mensagens acima.")