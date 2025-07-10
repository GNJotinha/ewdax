
import streamlit as st
import pandas as pd
import gdown
import unicodedata
from datetime import datetime
from difflib import get_close_matches

# ===== LOGIN COM NÍVEIS (st.secrets) =====
USUARIOS = st.secrets.get("USUARIOS", {})

def autenticar(usuario, senha):
    return usuario in USUARIOS and USUARIOS[usuario]["senha"] == senha

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario = ""

if not st.session_state.logado:
    st.title("Login do Painel")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if autenticar(usuario, senha):
            st.session_state.logado = True
            st.session_state.usuario = usuario
        else:
            st.error("Usuário ou senha incorretos")
    st.stop()

# ===== CONFIGURAÇÕES E FUNÇÕES =====
st.set_page_config(page_title="Painel Movee", page_icon="📊")
st.sidebar.success(f"Bem-vindo, {st.session_state.usuario}")

def normalizar(texto):
    if pd.isna(texto): return ""
    return unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode().lower().strip()

def tempo_para_segundos(t):
    if pd.isna(t): return 0
    try: return t.hour * 3600 + t.minute * 60 + t.second
    except AttributeError: return int(t) if isinstance(t, (int, float)) else 0

# ===== DADOS =====
@st.cache_data
def carregar_dados():
    url = "https://drive.google.com/uc?id=1Dmmg1R-xmmC0tfi5-1GVS8KLqhZJUqm5"
    output = "Calendarios.xlsx"
    gdown.download(url, output, quiet=True)
    df = pd.read_excel(output, sheet_name="Base 2025")
    df["data_do_periodo"] = pd.to_datetime(df["data_do_periodo"])
    df["data"] = df["data_do_periodo"].dt.date
    df["data_datetime"] = pd.to_datetime(df["data"])
    df["mes"] = df["data_do_periodo"].dt.month
    df["ano"] = df["data_do_periodo"].dt.year
    df["pessoa_entregadora_normalizado"] = df["pessoa_entregadora"].apply(normalizar)
    return df

df = carregar_dados()
entregadores = sorted(df["pessoa_entregadora"].dropna().unique().tolist())

# ===== INTERFACE PRINCIPAL =====
st.title("Relatório de Entregadores")

with st.sidebar.expander("📊 NÚMEROS ENTREGADORES", expanded=True):
    modo = st.radio("", ["Ver 1 mês", "Ver 2 meses", "Ver geral", "Simplificada (WhatsApp)"])

def gerar_texto(nome, periodo, dias_esperados, presencas, faltas, tempo_pct,
                turnos, ofertadas, aceitas, rejeitadas, completas,
                tx_aceitas, tx_rejeitadas, tx_completas):
    return f"""{nome} – {periodo}

Dias esperados: {dias_esperados}
Presenças: {presencas}
Faltas: {faltas}
Tempo online: {tempo_pct}%
Turnos no mês: {turnos}
Corridas:
 • Ofertadas: {ofertadas}
 • Aceitas: {aceitas} ({tx_aceitas}%)
 • Rejeitadas: {rejeitadas} ({tx_rejeitadas}%)
 • Completas: {completas} ({tx_completas}%)
"""

def gerar_dados(nome, mes, ano, df):
    nome_norm = normalizar(nome)
    df["tempo_segundos"] = df["tempo_disponivel_absoluto"].apply(tempo_para_segundos)
    df["duracao_segundos"] = df["duracao_do_periodo"].apply(tempo_para_segundos)
    dados = df[(df["pessoa_entregadora_normalizado"] == nome_norm) &
               (df["mes"] == mes) & (df["ano"] == ano)]
    if dados.empty:
        return None
    tempo_disp = dados["tempo_segundos"].mean()
    duracao_media = dados["duracao_segundos"].mean()
    tempo_pct = round(tempo_disp / duracao_media * 100, 1) if duracao_media else 0.0
    presencas = dados["data"].nunique()
    dias_no_mes = pd.date_range(start=f"{ano}-{mes:02d}-01", periods=31, freq="D")
    dias_no_mes = dias_no_mes[dias_no_mes.month == mes]
    faltas = len(dias_no_mes) - presencas
    ofertadas = int(dados["numero_de_corridas_ofertadas"].sum())
    aceitas = int(dados["numero_de_corridas_aceitas"].sum())
    rejeitadas = int(dados["numero_de_corridas_rejeitadas"].sum())
    completas = int(dados["numero_de_corridas_completadas"].sum())
    tx_aceitas = round(aceitas / ofertadas * 100, 1) if ofertadas else 0.0
    tx_rejeitadas = round(rejeitadas / ofertadas * 100, 1) if ofertadas else 0.0
    tx_completas = round(completas / aceitas * 100, 1) if aceitas else 0.0
    meses_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    periodo = f"{meses_pt[mes - 1]}/{ano}"
    return gerar_texto(nome, periodo, len(dias_no_mes), presencas, faltas, tempo_pct,
                       presencas, ofertadas, aceitas, rejeitadas, completas,
                       tx_aceitas, tx_rejeitadas, tx_completas)

# ===== FORMULÁRIO =====
st.markdown("### Buscar entregador")
nome_digitado = st.text_input("Digite o nome:")
sugeridos = get_close_matches(nome_digitado, entregadores, n=1, cutoff=0.5)
if sugeridos:
    nome = sugeridos[0]
    st.markdown(f"**Nome detectado:** {nome}")
else:
    nome = ""

if nome:
    with st.form("formulario"):
        if modo == "Ver 1 mês":
            col1, col2 = st.columns(2)
            mes = col1.selectbox("Mês:", list(range(1, 13)))
            ano = col2.selectbox("Ano:", sorted(df["ano"].unique(), reverse=True))
        elif modo == "Ver 2 meses":
            col1, col2 = st.columns(2)
            mes1 = col1.selectbox("1º Mês:", list(range(1, 13)), key="mes1")
            ano1 = col2.selectbox("1º Ano:", sorted(df["ano"].unique(), reverse=True), key="ano1")
            mes2 = col1.selectbox("2º Mês:", list(range(1, 13)), key="mes2")
            ano2 = col2.selectbox("2º Ano:", sorted(df["ano"].unique(), reverse=True), key="ano2")
        gerar = st.form_submit_button("Gerar relatório")

    if gerar:
        with st.spinner("Processando..."):
            if modo == "Ver 1 mês":
                texto = gerar_dados(nome, mes, ano, df)
                st.text_area("Resultado:", value=texto or "Nenhum dado encontrado", height=350)
            elif modo == "Ver 2 meses":
                t1 = gerar_dados(nome, mes1, ano1, df)
                t2 = gerar_dados(nome, mes2, ano2, df)
                resultado = (t1 or "") + "

" + (t2 or "")
                st.text_area("Resultado:", value=resultado if resultado.strip() else "Nenhum dado encontrado", height=700)
            elif modo == "Ver geral":
                st.warning("Relatório geral ainda será implementado.")
            elif modo == "Simplificada (WhatsApp)":
                st.warning("Relatório simplificado ainda será implementado.")

# (Mantém toda a parte anterior igual, apenas continua e finaliza aqui...)

def gerar_geral(nome, df):
    nome_norm = normalizar(nome)
    dados = df[df["pessoa_entregadora_normalizado"] == nome_norm]
    if dados.empty:
        return None
    dados["tempo_segundos"] = dados["tempo_disponivel_absoluto"].apply(tempo_para_segundos)
    dados["duracao_segundos"] = dados["duracao_do_periodo"].apply(tempo_para_segundos)
    tempo_disp = dados["tempo_segundos"].mean()
    duracao_media = dados["duracao_segundos"].mean()
    tempo_pct = round(tempo_disp / duracao_media * 100, 1) if duracao_media else 0.0
    presencas = dados["data"].nunique()
    min_data = dados["data"].min()
    max_data = dados["data"].max()
    dias_esperados = (max_data - min_data).days + 1
    faltas = dias_esperados - presencas
    ofertadas = int(dados["numero_de_corridas_ofertadas"].sum())
    aceitas = int(dados["numero_de_corridas_aceitas"].sum())
    rejeitadas = int(dados["numero_de_corridas_rejeitadas"].sum())
    completas = int(dados["numero_de_corridas_completadas"].sum())
    tx_aceitas = round(aceitas / ofertadas * 100, 1) if ofertadas else 0.0
    tx_rejeitadas = round(rejeitadas / ofertadas * 100, 1) if ofertadas else 0.0
    tx_completas = round(completas / aceitas * 100, 1) if aceitas else 0.0
    periodo = f"{min_data.strftime('%d/%m/%Y')} a {max_data.strftime('%d/%m/%Y')}"
    return gerar_texto(nome, periodo, dias_esperados, presencas, faltas, tempo_pct,
                       presencas, ofertadas, aceitas, rejeitadas, completas,
                       tx_aceitas, tx_rejeitadas, tx_completas)

def gerar_simplificado(nome, df):
    nome_norm = normalizar(nome)
    df = df[df["pessoa_entregadora_normalizado"] == nome_norm]
    if df.empty:
        return None
    df["tempo_segundos"] = df["tempo_disponivel_absoluto"].apply(tempo_para_segundos)
    df["duracao_segundos"] = df["duracao_do_periodo"].apply(tempo_para_segundos)
    df["mes_ano"] = df["data_datetime"].dt.to_period("M")
    ultimos_meses = sorted(df["mes_ano"].unique())[-2:]
    textos = []
    for periodo in ultimos_meses:
        dados = df[df["mes_ano"] == periodo]
        if dados.empty:
            continue
        mes = periodo.month
        ano = periodo.year
        tempo_disp = dados["tempo_segundos"].mean()
        duracao_media = dados["duracao_segundos"].mean()
        tempo_pct = round(tempo_disp / duracao_media * 100, 1) if duracao_media else 0.0
        turnos = dados.shape[0]
        ofertadas = int(dados["numero_de_corridas_ofertadas"].sum())
        aceitas = int(dados["numero_de_corridas_aceitas"].sum())
        rejeitadas = int(dados["numero_de_corridas_rejeitadas"].sum())
        completas = int(dados["numero_de_corridas_completadas"].sum())
        tx_aceitas = round(aceitas / ofertadas * 100, 1) if ofertadas else 0.0
        tx_rejeitadas = round(rejeitadas / ofertadas * 100, 1) if ofertadas else 0.0
        tx_completas = round(completas / aceitas * 100, 1) if aceitas else 0.0
        meses_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        periodo_str = f"{meses_pt[mes - 1]}/{ano}"
        texto = f"""{nome} – {periodo_str}
Tempo online: {tempo_pct}%
Turnos realizados: {turnos}
Corridas:
 • Ofertadas: {ofertadas}
 • Aceitas: {aceitas} ({tx_aceitas}%)
 • Rejeitadas: {rejeitadas} ({tx_rejeitadas}%)
 • Completas: {completas} ({tx_completas}%)
"""
        textos.append(texto)
    return "
---
".join(textos)
