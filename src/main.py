from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode, quote
import requests
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import sys
import holidays
import random
from pathlib import Path
import html
from email.utils import make_msgid
load_dotenv()

def buscar_sgs(codigo):
    hoje = date.today()
    inicio = hoje - timedelta(days=120)
    url = (
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
        f"?formato=json&dataInicial={inicio:%d/%m/%Y}&dataFinal={hoje:%d/%m/%Y}"
    )
    resposta = requests.get(url, timeout=30)
    resposta.raise_for_status()
    try:
        dados = resposta.json()
    except ValueError:
        raise ValueError(f"SGS {codigo} não devolveu JSON: {resposta.text[:80]!r}")
    anterior, atual = dados[-2], dados[-1]
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

def buscar_ibovespa():
    token = os.environ["BRAPI_TOKEN"]
    url = "https://brapi.dev/api/quote/%5EBVSP"
    cabecalho = {"Authorization": f"Bearer {token}"}
    resposta = requests.get(url, headers=cabecalho, timeout=30)
    resposta.raise_for_status()
    cotacao = resposta.json()["results"][0]
    return (cotacao["regularMarketTime"],
            cotacao["regularMarketPrice"],
            cotacao["regularMarketChangePercent"])
    
def frase_do_dia():
    arquivo = Path(__file__).parent.parent / "frases.txt"
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    frases = [l.strip() for l in linhas if l.strip()]
    return random.choice(frases)    

def montar_mensagem():
    series = {
        "Meta Selic (% a.a.)": 432,
        "IPCA mensal (%)": 433,
        "IPCA 12 meses (%)": 13522,
        "Dólar PTAX (R$)": 1,
    }
    linhas = [f"Boletim Macro do Guigas | {date.today():%d/%m/%Y}", "", f'"{frase_do_dia()}"', ""]
    falhas = []

    for nome, codigo in series.items():
        try:
            data, valor, anterior = buscar_sgs(codigo)
        except Exception as erro:
            linhas.append(f"{nome}: indisponível hoje")
            falhas.append(f"{nome} (SGS {codigo}): {erro}")
            continue
        variacao = valor - anterior
        linhas.append(f"{nome}: {valor:.2f} ({variacao:+.2f}) em {data}")

    try:
        data, pontos, var_pct = buscar_ibovespa()
    except Exception as erro:
        linhas.append("Ibovespa: indisponível hoje")
        falhas.append(f"Ibovespa (brapi): {erro}")
    else:
        brasilia = timezone(timedelta(hours=-3))
        momento = datetime.fromisoformat(data).astimezone(brasilia)
        pontos_br = f"{pontos:,.0f}".replace(",", ".")
        linhas.append(f"Ibovespa (pts): {pontos_br} ({var_pct:+.2f}%) em {momento:%d/%m/%Y %Hh%M}")

    linhas.append("")
    linhas.append("Focus, mediana para 2027:")
    for indicador in ["IPCA", "Selic"]:
        try:
            data, mediana = buscar_focus(indicador, 2027)
        except Exception as erro:
            linhas.append(f"{indicador}: indisponível hoje")
            falhas.append(f"Focus {indicador}: {erro}")
            continue
        linhas.append(f"{indicador}: {mediana:.2f}")

    if falhas:
        linhas.append("")
        linhas.append("Avisos técnicos:")
        for falha in falhas:
            linhas.append(f"- {falha}")

    return "\n".join(linhas)

def montar_html(texto, cid_onda):
    linhas = texto.split("\n")
    titulo = linhas[0]
    corpo = []
    for linha in linhas[1:]:
        linha = html.escape(linha)          # troca < > & por códigos seguros
        if linha == "":
            corpo.append('<tr><td style="height:12px"></td></tr>')
        elif linha.endswith(":"):           # títulos de bloco, ex.: "Focus, mediana para 2027:"
            corpo.append(
                '<tr><td style="padding:8px 24px 2px; font-weight:bold; color:#0b3d5c;">'
                f"{linha}</td></tr>"
            )
        elif linha.startswith("&quot;"):    # a frase do dia (começa com aspas)
            corpo.append(
                '<tr><td style="padding:4px 24px; font-style:italic; color:#4a6b7c;">'
                f"{linha}</td></tr>"
            )
        else:
            corpo.append(
                f'<tr><td style="padding:2px 24px; color:#1c2b33;">{linha}</td></tr>'
            )

    return f"""\
<html>
  <body style="margin:0; padding:0; background:#e9f1f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#e9f1f5;">
      <tr><td align="center" style="padding:16px 0;">
        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#ffffff; font-family:Arial, sans-serif; font-size:15px;">
          <tr><td style="background:#0b3d5c; padding:20px 24px; color:#ffffff;
                         font-size:20px; font-weight:bold;">{html.escape(titulo)}</td></tr>
          <tr><td style="line-height:0;">
            <img src="cid:{cid_onda}" width="600" height="110" alt="onda" style="display:block;">
          </td></tr>
          {"".join(corpo)}
          <tr><td style="height:20px"></td></tr>
          <tr><td style="background:#f3e9d2; padding:12px 24px; color:#7a6a4f; font-size:12px;">
            Dados: Banco Central (SGS e Focus) e brapi.dev
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


def enviar_email(texto, com_html=True):
    remetente = os.environ["BOLETIM_REMETENTE"]
    senha = os.environ["BOLETIM_SENHA"]
    destino = os.environ["BOLETIM_DESTINO"]

    msg = EmailMessage()
    msg["Subject"] = f"Boletim Macro do Guigas | {date.today():%d/%m/%Y}"
    msg["From"] = remetente
    msg["To"] = destino
    msg.set_content(texto)

    if com_html:
        cid = make_msgid(domain="boletim")
        msg.add_alternative(montar_html(texto, cid[1:-1]), subtype="html")
        gif = Path(__file__).parent.parent / "img" / "onda.gif"
        msg.get_payload()[1].add_related(
            gif.read_bytes(), maintype="image", subtype="gif", cid=cid
        )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
        servidor.login(remetente, senha)
        servidor.send_message(msg)
                
hoje = date.today()
feriados = holidays.financial_holidays("BVMF")
if hoje in feriados:
    print(f"Hoje é feriado na B3 ({feriados.get(hoje)}). Sem boletim.")
    sys.exit()
            
try:
    texto = montar_mensagem()
except Exception as erro:
    texto = f"O boletim de hoje falhou ao buscar os dados.\n\nErro: {erro}"

print(texto)
enviar_email(texto)
print("E-mail enviado!")
