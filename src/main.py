import requests

url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"
resposta = requests.get(url)       # faz o pedido, como o navegador
dados = resposta.json()            # converte o texto JSON em lista/dicionário Python

print(dados)                       # olhe o formato cru primeiro

ultimo = dados[0]                # pegue o primeiro item da lista
selic = float(ultimo["valor"])         # pegue o valor e converta para número

print(f"Meta Selic em {ultimo['data']}: {selic:.2f}% a.a.")

