import requests
from urllib.parse import urlencode, quote

def buscar_sgs(codigo):
    """Busca a última observação de uma série do SGS."""
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/1?formato=json"
    resposta = requests.get(url, timeout=30)
    resposta.raise_for_status()          # se a API falhar, para aqui com um erro claro
    ultimo = resposta.json()[0]
    return ultimo["data"], float(ultimo["valor"])

def buscar_focus(indicador, ano):
    """Mediana mais recente do Focus para um indicador e um ano."""
    url = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
    params = {
        "$filter": f"Indicador eq '{indicador}' and DataReferencia eq '{ano}' and baseCalculo eq 0",
        "$orderby": "Data desc",
        "$top": 1,
        "$format": "json",
    }
    resposta = requests.get(url + "?" + urlencode(params, quote_via=quote), timeout=30)
    resposta.raise_for_status()
    ultimo = resposta.json()["value"][0]
    return ultimo["Data"], ultimo["Mediana"]

series = {
    "Meta Selic (% a.a.)": 432,
    "IPCA mensal (%)": 433,
    "IPCA 12 meses (%)": 13522,
    "Dólar PTAX venda (R$)": 1,
}

for nome, codigo in series.items():
    data, valor = buscar_sgs(codigo)
    print(f"{nome}: {valor:.2f} em {data}")
    
for indicador in ["IPCA", "Selic"]:
    data, mediana = buscar_focus(indicador, 2027)
    print(f"Focus {indicador} 2027: {mediana:.2f} (pesquisa de {data})")