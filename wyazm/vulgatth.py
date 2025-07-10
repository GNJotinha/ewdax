import streamlit as st
import pandas as pd
import gdown
import unicodedata
from datetime import datetime, timedelta

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
        if autenticar(usuario, senha):
            st.session_state.logado = True
            st.session_state.usuario = usuario
        else:
            st.error("Usuário ou senha incorretos")
    st.stop()

# ===== CONFIG INICIAL =====
st.set_page_config(page_title="Painel Movee", page_icon="📊")
st.sidebar.success(f"Bem-vindo, {st.session_state.usuario} 👋")

# ===== FUNÇÕES UTILITÁRIAS =====
def normalizar(texto):
    if pd.isna(texto): return ""
    return unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode().lower().strip()

def tempo_para_segundos(t):
    if pd.isna(t): return 0
    try: return t.hour * 3600 + t.minute * 60 + t.second
    except AttributeError: return int(t) if isinstance(t, (int, float)) else 0

# ===== CARREGAR PLANILHA DO DRIVE =====
@st.cache_data
def carregar_dados():
    url = "https://drive.google.com/uc?id=1Dmmg1R-xmmC0tfi5-1GVS8KLqhZJUqm5"
    gdown.download(url, "Calendarios.xlsx", quiet=True)
    df = pd.read_excel("Calendarios.xlsx", sheet_name="Base 2025")
    df["data_do_periodo"] = pd.to_datetime(df["data_do_periodo"])
    df["data"] = df["data_do_periodo"].dt.date
    df["data_datetime"] = pd.to_datetime(df["data"])
    df["mes"] = df["data_do_periodo"].dt.month
    df["ano"] = df["data_do_periodo"].dt.year
    df["pessoa_entregadora_normalizado"] = df["pessoa_entregadora"].apply(normalizar)
    return df

df = carregar_dados()
entregadores = sorted(df["pessoa_entregadora"].dropna().unique())

# ===== FALTAS CONSECUTIVAS =====
def faltas_consecutivas(df, dias=30, limite=3):
    hoje = datetime.now().date()
    datas = pd.date_range(end=hoje - timedelta(days=1), periods=dias).date
    presencas = df.drop_duplicates(subset=["pessoa_entregadora", "data"])
    resultados = []

    for nome in df["pessoa_entregadora"].unique():
        if pd.isna(nome): continue
        entregador = presencas[presencas["pessoa_entregadora"] == nome]
        status = []
        for d in datas:
            presente = d in entregador["data"].values
            status.append("✔️" if presente else "❌")

        contagem = 0
        max_contagem = 0
        for s in status:
            if s == "❌":
                contagem += 1
                max_contagem = max(max_contagem, contagem)
            else:
                contagem = 0

        mes_atual = hoje.month
        atuou = any(entregador["data_datetime"].dt.month == mes_atual)
        if max_contagem >= limite and atuou:
            resultados.append(f"{nome} – {max_contagem} faltas seguidas")

    return resultados

# ===== INTERFACE =====
st.title("📋 Relatório de Entregadores")
with st.sidebar.expander("📊 NÚMEROS ENTREGADORES", expanded=True):
    modo = st.radio("", ["Ver 1 mês", "Ver 2 meses", "Ver geral", "Simplificada (WhatsApp)"])

# ===== GERADOR DE TEXTO =====
def gerar_texto(nome, periodo, dias_esperados, presencas, faltas, tempo_pct,
                turnos, ofertadas, aceitas, rejeitadas, completas,
                tx_aceitas, tx_rejeitadas, tx_completas):
    return f"""{nome} – {periodo}
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
    dados = df[(df["pessoa_entregadora_normalizado"] == nome_norm) &
               (df["mes"] == mes) & (df["ano"] == ano)]
    if dados.empty: return None
    dados["tempo_segundos"] = dados["tempo_disponivel_absoluto"].apply(tempo_para_segundos)
    dados["duracao_segundos"] = dados["duracao_do_periodo"].apply(tempo_para_segundos)
    tempo_pct = round(dados["tempo_segundos"].mean() / dados["duracao_segundos"].mean() * 100, 1)
    presencas = dados["data"].nunique()
    dias_mes = pd.date_range(start=f"{ano}-{mes:02d}-01", periods=31, freq="D")
    dias_mes = dias_mes[dias_mes.month == mes]
    faltas = len(dias_mes) - presencas
    ofertadas = int(dados["numero_de_corridas_ofertadas"].sum())
    aceitas = int(dados["numero_de_corridas_aceitas"].sum())
    rejeitadas = int(dados["numero_de_corridas_rejeitadas"].sum())
    completas = int(dados["numero_de_corridas_completadas"].sum())
    tx_aceitas = round(aceitas / ofertadas * 100, 1) if ofertadas else 0
    tx_rejeitadas = round(rejeitadas / ofertadas * 100, 1) if ofertadas else 0
    tx_completas = round(completas / aceitas * 100, 1) if aceitas else 0
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto",
             "Setembro","Outubro","Novembro","Dezembro"]
    periodo = f"{meses[mes-1]}/{ano}"
    return gerar_texto(nome, periodo, len(dias_mes), presencas, faltas, tempo_pct,
                       presencas, ofertadas, aceitas, rejeitadas, completas,
                       tx_aceitas, tx_rejeitadas, tx_completas)

# (continua em próxima célula por limite de tamanho)
def gerar_geral(nome, df):
    nome_norm = normalizar(nome)
    dados = df[df["pessoa_entregadora_normalizado"] == nome_norm]
    if dados.empty: return None
    dados["tempo_segundos"] = dados["tempo_disponivel_absoluto"].apply(tempo_para_segundos)
    dados["duracao_segundos"] = dados["duracao_do_periodo"].apply(tempo_para_segundos)
    tempo_pct = round(dados["tempo_segundos"].mean() / dados["duracao_segundos"].mean() * 100, 1)
    presencas = dados["data"].nunique()
    min_data = dados["data"].min()
    max_data = dados["data"].max()
    dias_esperados = (max_data - min_data).days + 1
    faltas = dias_esperados - presencas
    ofertadas = int(dados["numero_de_corridas_ofertadas"].sum())
    aceitas = int(dados["numero_de_corridas_aceitas"].sum())
    rejeitadas = int(dados["numero_de_corridas_rejeitadas"].sum())
    completas = int(dados["numero_de_corridas_completadas"].sum())
    tx_aceitas = round(aceitas / ofertadas * 100, 1) if ofertadas else 0
    tx_rejeitadas = round(rejeitadas / ofertadas * 100, 1) if ofertadas else 0
    tx_completas = round(completas / aceitas * 100, 1) if aceitas else 0
    periodo = f"{min_data.strftime('%d/%m/%Y')} a {max_data.strftime('%d/%m/%Y')}"
    return gerar_texto(nome, periodo, dias_esperados, presencas, faltas, tempo_pct,
                       presencas, ofertadas, aceitas, rejeitadas, completas,
                       tx_aceitas, tx_rejeitadas, tx_completas)

def gerar_simplificado(nome, df):
    nome_norm = normalizar(nome)
    df_entregador = df[df["pessoa_entregadora_normalizado"] == nome_norm]
    if df_entregador.empty: return "Nenhum dado encontrado"
    meses = sorted(df_entregador["data"].map(lambda x: x.replace(day=1)).unique())[-2:]
    textos = []
    for data_ref in meses:
        mes, ano = data_ref.month, data_ref.year
        dados = df_entregador[(df_entregador["mes"] == mes) & (df_entregador["ano"] == ano)]
        if dados.empty: continue
        dados["tempo_segundos"] = dados["tempo_disponivel_absoluto"].apply(tempo_para_segundos)
        dados["duracao_segundos"] = dados["duracao_do_periodo"].apply(tempo_para_segundos)
        tempo_pct = round(dados["tempo_segundos"].mean() / dados["duracao_segundos"].mean() * 100, 1)
        turnos = dados.shape[0]
        ofertadas = int(dados["numero_de_corridas_ofertadas"].sum())
        aceitas = int(dados["numero_de_corridas_aceitas"].sum())
        rejeitadas = int(dados["numero_de_corridas_rejeitadas"].sum())
        completas = int(dados["numero_de_corridas_completadas"].sum())
        tx_aceitas = round(aceitas / ofertadas * 100, 1) if ofertadas else 0
        tx_rejeitadas = round(rejeitadas / ofertadas * 100, 1) if ofertadas else 0
        tx_completas = round(completas / aceitas * 100, 1) if aceitas else 0
        meses_pt = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto",
                    "Setembro","Outubro","Novembro","Dezembro"]
        titulo = f"{nome} – {meses_pt[mes-1]}/{ano}"
        resumo = f"""{titulo}
Tempo online: {tempo_pct}%
Turnos realizados: {turnos}
Corridas:
• Ofertadas: {ofertadas}
• Aceitas: {aceitas} ({tx_aceitas}%)
• Rejeitadas: {rejeitadas} ({tx_rejeitadas}%)
• Completas: {completas} ({tx_completas}%)
"""
        textos.append(resumo)
    return "\n\n".join(textos)

# ===== INTERAÇÃO =====
nome = st.selectbox("Selecionar entregador:", [""] + list(entregadores))

if nome:
    if modo == "Ver 1 mês":
        col1, col2 = st.columns(2)
        mes = col1.selectbox("Mês:", list(range(1, 13)))
        ano = col2.selectbox("Ano:", sorted(df["ano"].unique(), reverse=True))
        if st.button("Gerar"):
            st.text_area("Resultado:", gerar_dados(nome, mes, ano, df), height=350)

    elif modo == "Ver 2 meses":
        col1, col2 = st.columns(2)
        mes1 = col1.selectbox("1º Mês:", list(range(1, 13)), key="mes1")
        ano1 = col2.selectbox("1º Ano:", sorted(df["ano"].unique(), reverse=True), key="ano1")
        mes2 = col1.selectbox("2º Mês:", list(range(1, 13)), key="mes2")
        ano2 = col2.selectbox("2º Ano:", sorted(df["ano"].unique(), reverse=True), key="ano2")
        if st.button("Gerar"):
            t1 = gerar_dados(nome, mes1, ano1, df)
            t2 = gerar_dados(nome, mes2, ano2, df)
            st.text_area("Resultado:", (t1 or "") + "\n\n" + (t2 or ""), height=700)

    elif modo == "Ver geral":
        if st.button("Gerar"):
            st.text_area("Resultado:", gerar_geral(nome, df), height=450)

    elif modo == "Simplificada (WhatsApp)":
        if st.button("Gerar"):
            st.text_area("Resultado:", gerar_simplificado(nome, df), height=600)

# ===== ALERTA DE FALTAS (VISÍVEL APENAS PARA ADMIN) =====
if USUARIOS.get(st.session_state.usuario, {}).get("nivel") == "admin":
    st.sidebar.markdown("### ⚠️ Alerta de Faltas")
    alertas = faltas_consecutivas(df)
    if alertas:
        for nome in alertas:
            st.sidebar.warning(nome)
    else:
        st.sidebar.info("Nenhum entregador com faltas consecutivas")
