import streamlit as st
import pandas as pd
import gdown
import unicodedata
from datetime import datetime

# ===== CONFIGURAÇÕES =====
st.set_page_config(page_title="Painel de Entregadores", page_icon="📋")

# ===== LOGIN =====
USUARIOS = st.secrets.get("USUARIOS", {})

def autenticar(usuario, senha):
    return usuario in USUARIOS and USUARIOS[usuario]["senha"] == senha

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario = ""

if not st.session_state.logado:
    st.title("🔐 Login do Painel")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if autenticar(usuario.lower(), senha):
            st.session_state.logado = True
            st.session_state.usuario = usuario
        else:
            st.error("Usuário ou senha incorretos")
    st.stop()

st.sidebar.success(f"Bem-vindo, {st.session_state.usuario}!")

# ===== FUNÇÕES =====
def normalizar(texto):
    if pd.isna(texto): return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode().lower().strip()

def tempo_para_segundos(t):
    if pd.isna(t): return 0
    try: return t.hour * 3600 + t.minute * 60 + t.second
    except AttributeError: return int(t) if isinstance(t, (int, float)) else 0

def gerar_texto(nome, periodo, dias_esperados, presencas, faltas, tempo_pct,
                turnos, ofertadas, aceitas, rejeitadas, completas,
                tx_aceitas, tx_rejeitadas, tx_completas):
    return f"""📋 {nome} – {periodo}

📆 Dias esperados: {dias_esperados}
✅ Presenças: {presencas}
❌ Faltas: {faltas}

⏱️ Tempo online: {tempo_pct}%

🧾 Turnos realizados: {turnos}

🚗 Corridas:
• 📦 Ofertadas: {ofertadas}
• 👍 Aceitas: {aceitas} ({tx_aceitas}%)
• 👎 Rejeitadas: {rejeitadas} ({tx_rejeitadas}%)
• 🏁 Completas: {completas} ({tx_completas}%)
"""

def gerar_dados(nome, mes, ano, df):
    nome_norm = normalizar(nome)
    df["tempo_segundos"] = df["tempo_disponivel_absoluto"].apply(tempo_para_segundos)
    df["duracao_segundos"] = df["duracao_do_periodo"].apply(tempo_para_segundos)
    dados = df[(df["pessoa_entregadora_normalizado"] == nome_norm) &
               (df["mes"] == mes) & (df["ano"] == ano)]
    if dados.empty: return None

    tempo_disp = dados["tempo_segundos"].mean()
    duracao_media = dados["duracao_segundos"].mean()
    tempo_pct = round(tempo_disp / duracao_media * 100, 1) if duracao_media else 0.0

    presencas = dados["data"].nunique()
    dias_no_mes = pd.date_range(start=f"{ano}-{mes:02d}-01", periods=31, freq='D')
    dias_no_mes = dias_no_mes[dias_no_mes.month == mes]
    faltas = len(dias_no_mes) - presencas
    turnos = presencas

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
                       turnos, ofertadas, aceitas, rejeitadas, completas,
                       tx_aceitas, tx_rejeitadas, tx_completas)

def gerar_geral(nome, df):
    nome_norm = normalizar(nome)
    dados = df[df["pessoa_entregadora_normalizado"] == nome_norm]
    if dados.empty: return None

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

# ===== LEITURA DO ARQUIVO DO DRIVE =====
@st.cache_data
def carregar_dados():
    file_id = "1Dmmg1R-xmmC0tfi5-1GVS8KLqhZJUqm5"
    url = f"https://drive.google.com/uc?id={file_id}"
    gdown.download(url, "Calendarios.xlsx", quiet=True)
    df = pd.read_excel("Calendarios.xlsx", sheet_name="Base 2025")
    df["data_do_periodo"] = pd.to_datetime(df["data_do_periodo"])
    df["data"] = df["data_do_periodo"].dt.date
    df["mes"] = df["data_do_periodo"].dt.month
    df["ano"] = df["data_do_periodo"].dt.year
    df["pessoa_entregadora_normalizado"] = df["pessoa_entregadora"].apply(normalizar)
    return df

# ===== INTERFACE PRINCIPAL =====
df = carregar_dados()
entregadores = [""] + sorted(df["pessoa_entregadora"].dropna().unique().tolist())

st.title("📋 Relatório de Entregadores")
modo = st.radio("Selecione o tipo de relatório:", ["Ver 1 mês", "Comparar 2 meses", "Ver geral"])

with st.form("formulario"):
    nome = st.selectbox("Nome do entregador:", entregadores)

    if modo == "Ver 1 mês":
        col1, col2 = st.columns(2)
        mes = col1.selectbox("Mês:", list(range(1, 13)))
        ano = col2.selectbox("Ano:", sorted(df["ano"].unique(), reverse=True))

    elif modo == "Comparar 2 meses":
        col1, col2 = st.columns(2)
        mes1 = col1.selectbox("1º Mês:", list(range(1, 13)), key="mes1")
        ano1 = col2.selectbox("1º Ano:", sorted(df["ano"].unique(), reverse=True), key="ano1")
        mes2 = col1.selectbox("2º Mês:", list(range(1, 13)), key="mes2")
        ano2 = col2.selectbox("2º Ano:", sorted(df["ano"].unique(), reverse=True), key="ano2")

    gerar = st.form_submit_button("🔍 Gerar relatório")

if gerar and nome != "":
    with st.spinner("Gerando relatório..."):
        if modo == "Ver 1 mês":
            texto = gerar_dados(nome, mes, ano, df)
            st.text_area("Resultado:", value=texto or "❌ Nenhum dado encontrado", height=350)

        elif modo == "Comparar 2 meses":
            t1 = gerar_dados(nome, mes1, ano1, df)
            t2 = gerar_dados(nome, mes2, ano2, df)
            if t1 or t2:
                st.text_area("Resultado:", value=(t1 or "") + "\n\n" + (t2 or ""), height=700)
            else:
                st.error("❌ Nenhum dado encontrado para os dois meses")

        elif modo == "Ver geral":
            texto = gerar_geral(nome, df)
            st.text_area("Resultado:", value=texto or "❌ Nenhum dado encontrado", height=400)

        st.success("✅ Pronto! Copie e cole no WhatsApp.")