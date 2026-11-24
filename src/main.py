from datetime import date
from urllib.parse import urlencode, quote
import requests
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
load_dotenv()

def buscar_sgs(codigo):
    """Últimas 2 observações de uma série do SGS: data, valor atual e anterior."""
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/2?formato=json"
    resposta = requests.get(url, timeout=30)
    resposta.raise_for_status()
    anterior, atual = resposta.json()        # a lista vem em ordem: mais antiga primeiro
    return atual["data"], float(atual["valor"]), float(anterior["valor"])

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

def montar_mensagem():
    series = {
        "Meta Selic (% a.a.)": 432,
        "IPCA mensal (%)": 433,
        "IPCA 12 meses (%)": 13522,
        "Dólar PTAX (R$)": 1,
    }
    linhas = [f"Boletim Macro do Guigas | {date.today():%d/%m/%Y}", ""]

    for nome, codigo in series.items():
        data, valor, anterior = buscar_sgs(codigo)
        variacao = valor - anterior
        linhas.append(f"{nome}: {valor:.2f} ({variacao:+.2f}) em {data}")

    linhas.append("")
    linhas.append("Focus, mediana para 2027:")
    for indicador in ["IPCA", "Selic"]:
        data, mediana = buscar_focus(indicador, 2027)
        linhas.append(f"{indicador}: {mediana:.2f}")

    return "\n".join(linhas)

def enviar_email(texto):
    """Envia o boletim pelo Gmail usando a senha de app."""
    remetente = os.environ["BOLETIM_REMETENTE"]
    senha = os.environ["BOLETIM_SENHA"]
    destino = os.environ["BOLETIM_DESTINO"]

    msg = EmailMessage()
    msg["Subject"] = f"Boletim Macro do Guigas | {date.today():%d/%m/%Y}"
    msg["From"] = remetente
    msg["To"] = destino
    msg.set_content(texto)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
        servidor.login(remetente, senha)
        servidor.send_message(msg)
        
try:
    texto = montar_mensagem()
except Exception as erro:
    texto = f"O boletim de hoje falhou ao buscar os dados.\n\nErro: {erro}"

print(texto)
enviar_email(texto)
print("E-mail enviado!")
print(texto)
enviar_email(texto)
print("E-mail enviado!")
