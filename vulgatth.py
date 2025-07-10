import streamlit as st
import pandas as pd
import gdown
import unicodedata
from datetime import datetime, timedelta

# ===== LOGIN COM NÍVEIS =====
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
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos")
    st.stop()

# ===== CONFIGURAÇÃO INICIAL =====
st.set_page_config(page_title="Painel de Entregadores", page_icon="📋")
st.sidebar.success(f"Bem-vindo, {st.session_state.usuario}!")

# ===== MENU LATERAL =====
st.sidebar.title("NÚMEROS ENTREGADORES")
modo = st.sidebar.radio("Escolha uma opção:", [
    "Ver 1 mês",
    "Ver 2 meses",
    "Ver geral",
    "Simplicada (WhatsApp)",
    "Alertas de Faltas"
])

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
    dados = df[(df["pessoa_entregadora_normalizado"] == nome_norm)]
    if mes and ano:
        dados = dados[(df["mes"] == mes) & (df["ano"] == ano)]
    if dados.empty:
        return None

    tempo_disp = dados["tempo_segundos"].mean()
    duracao_media = dados["duracao_segundos"].mean()
    tempo_pct = round(tempo_disp / duracao_media * 100, 1) if duracao_media else 0.0

    presencas = dados["data"].nunique()
    if mes and ano:
        dias_no_mes = pd.date_range(start=f"{ano}-{mes:02d}-01", periods=31, freq='D')
        dias_no_mes = dias_no_mes[dias_no_mes.month == mes]
        faltas = len(dias_no_mes) - presencas
        dias_esperados = len(dias_no_mes)
    else:
        min_data = dados["data"].min()
        max_data = dados["data"].max()
        dias_esperados = (max_data - min_data).days + 1
        faltas = dias_esperados - presencas

    turnos = len(dados)

    ofertadas = int(dados["numero_de_corridas_ofertadas"].sum())
    aceitas = int(dados["numero_de_corridas_aceitas"].sum())
    rejeitadas = int(dados["numero_de_corridas_rejeitadas"].sum())
    completas = int(dados["numero_de_corridas_completadas"].sum())

    tx_aceitas = round(aceitas / ofertadas * 100, 1) if ofertadas else 0.0
    tx_rejeitadas = round(rejeitadas / ofertadas * 100, 1) if ofertadas else 0.0
    tx_completas = round(completas / aceitas * 100, 1) if aceitas else 0.0

    if mes and ano:
        meses_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        periodo = f"{meses_pt[mes - 1]}/{ano}"
    else:
        min_data = dados["data"].min().strftime('%d/%m/%Y')
        max_data = dados["data"].max().strftime('%d/%m/%Y')
        periodo = f"{min_data} a {max_data}"

    return gerar_texto(nome, periodo, dias_esperados, presencas, faltas, tempo_pct,
                       turnos, ofertadas, aceitas, rejeitadas, completas,
                       tx_aceitas, tx_rejeitadas, tx_completas)

# ===== CARREGAR DADOS DO GOOGLE DRIVE =====
@st.cache_data
def carregar_dados():
    file_id = "1Dmmg1R-xmmC0tfi5-1GVS8KLqhZJUqm5"
    url = f"https://drive.google.com/uc?id={file_id}"
    output = "Calendarios.xlsx"
    gdown.download(url, output, quiet=True)
    df = pd.read_excel(output, sheet_name="Base 2025")
    df["data_do_periodo"] = pd.to_datetime(df["data_do_periodo"])
    df["data"] = df["data_do_periodo"].dt.date
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
df["mes"] = df["data_do_periodo"].dt.month
    df["ano"] = df["data_do_periodo"].dt.year
    df["pessoa_entregadora_normalizado"] = df["pessoa_entregadora"].apply(normalizar)
    return df

df = carregar_dados()
entregadores = [""] + sorted(df["pessoa_entregadora"].dropna().unique().tolist())

# ===== ATUALIZAR DADOS (apenas admin) =====
nivel = USUARIOS.get(st.session_state.usuario, {}).get("nivel", "")
if nivel == "admin":
    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()
        st.rerun()

# ===== FORMULÁRIO =====
if modo in ["Ver 1 mês", "Ver 2 meses", "Ver geral", "Simplicada (WhatsApp)"]:
    with st.form("formulario"):
        nome = st.selectbox("Nome do entregador:", entregadores)

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

        gerar = st.form_submit_button
    # Simplicada não usa seleção de mês/ano("🔍 Gerar relatório")

    if gerar and nome:
        with st.spinner("Gerando relatório..."):
            if modo == "Ver 1 mês":
                texto = gerar_dados(nome, mes, ano, df)
                st.text_area("Resultado:", value=texto or "❌ Nenhum dado encontrado", height=350)

            elif modo == "Ver 2 meses":
                t1 = gerar_dados(nome, mes1, ano1, df)
                t2 = gerar_dados(nome, mes2, ano2, df)
                if t1 or t2:
                    st.text_area("Resultado:", value=(t1 or "") + "\n\n" + (t2 or ""), height=700)
                else:
                    st.error("❌ Nenhum dado encontrado para os dois meses")

            elif modo == "Ver geral":
                texto = gerar_dados(nome, None, None, df[df["pessoa_entregadora"] == nome])
                st.text_area("Resultado:", value=texto or "❌ Nenhum dado encontrado", height=400)

        elif modo == "Simplicada (WhatsApp)":
            texto = gerar_simplificado(nome, df)
            st.text_area("Resultado:", value=texto or "❌ Nenhum dado encontrado", height=500)

            elif modo == "Simplicada (WhatsApp)":textos = [gerar_dados(nome, m.month, m.year, df) for m in meses]
                st.text_area("Resultado:", value="\n\n".join([t for t in textos if t]), height=700)

# ===== ALERTAS DE FALTAS =====
if modo == "Alertas de Faltas":
    st.subheader("⚠️ Entregadores com 3+ faltas consecutivas")
    hoje = datetime.now().date()
    ultimos_15_dias = hoje - timedelta(days=15)

    ativos = df[df["data"] >= ultimos_15_dias]["pessoa_entregadora_normalizado"].unique()
    mensagens = []

    for nome in ativos:
        entregador = df[df["pessoa_entregadora_normalizado"] == nome]
        if entregador.empty:
            continue

        dias = pd.date_range(end=hoje - timedelta(days=1), periods=30).date
        presencas = set(entregador["data"])

        sequencia = 0
        for dia in sorted(dias):
            if dia in presencas:
                sequencia = 0
            else:
                sequencia += 1

        if sequencia >= 3:
            nome_original = entregador["pessoa_entregadora"].iloc[0]
            mensagens.append(
                f"• {nome_original} – {sequencia} dias consecutivos ausente (última presença: {entregador['data'].max().strftime('%d/%m')})"
            )

    if mensagens:
        st.text_area("Resultado:", value="\n".join(mensagens), height=400)
    else:
        st.success("✅ Nenhum entregador ativo com faltas consecutivas.")
