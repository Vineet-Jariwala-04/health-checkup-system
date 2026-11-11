"""Design tokens + CSS for the AHV Hospital frontend (light / dark, 3 text sizes)."""
import streamlit as st

TEXT_SIZES = {"Small": 15, "Medium": 16, "Large": 18}

LIGHT = dict(
    bg1="#f0fbfc", bg2="#e3f4f6", card="#ffffff", field="#f4f9fa", text="#0f2a33",
    muted="#4b6670", border="#cfe3e8", primary="#0e7490", primary_hover="#155e75",
    on_primary="#ffffff", ring="#0891b2", ok="#047857", ok_bg="#dcfce7",
    bad="#b91c1c", bad_bg="#fee2e2", warn="#92400e", warn_bg="#fef3c7", info_bg="#e0f2fe", info="#075985",
    shadow="0 24px 60px -24px rgba(8,75,95,.35)", track="#d5e5e9",
)
DARK = dict(
    bg1="#081418", bg2="#0b1d23", card="#10262d", field="#0b1c22", text="#e6f4f7",
    muted="#9ab7bf", border="#26434c", primary="#22d3ee", primary_hover="#67e8f9",
    on_primary="#04222a", ring="#67e8f9", ok="#4ade80", ok_bg="#12341f",
    bad="#fca5a5", bad_bg="#3b1616", warn="#fcd34d", warn_bg="#3a2e0e", info_bg="#0e2d3d", info="#7dd3fc",
    shadow="0 24px 60px -24px rgba(0,0,0,.7)", track="#22404a",
)


def init():
    st.session_state.setdefault("dark", False)
    st.session_state.setdefault("text_size", "Medium")


def is_dark():
    return bool(st.session_state.get("dark"))


def _flip_theme():
    st.session_state.dark = not st.session_state.dark


def theme_button():
    st.button("", key="theme_btn", on_click=_flip_theme,
              icon=":material/light_mode:" if is_dark() else ":material/dark_mode:",
              help="Switch to light mode" if is_dark() else "Switch to dark mode")


def text_size_popover():
    with st.popover("", icon=":material/text_fields:", help="Text size"):
        st.radio("Text size", list(TEXT_SIZES), key="text_size", horizontal=True)


def theme_controls():
    """Icon button (dark/light) + 'Aa' popover for text size."""
    with st.container(key="theme_row"):
        c1, c2, _ = st.columns([1, 1, 6])
        with c1:
            st.button("", key="theme_btn", on_click=_flip_theme,
                      icon=":material/light_mode:" if is_dark() else ":material/dark_mode:",
                      help="Switch to light mode" if is_dark() else "Switch to dark mode")
        with c2:
            with st.popover("", icon=":material/text_fields:", help="Text size"):
                st.radio("Text size", list(TEXT_SIZES), key="text_size", horizontal=True)


def inject():
    t = DARK if is_dark() else LIGHT
    size = TEXT_SIZES.get(st.session_state.get("text_size", "Medium"), 16)
    root = ":root{" + "".join(f"--{k.replace('_','-')}:{v};" for k, v in t.items()) + \
        f"color-scheme:{'dark' if is_dark() else 'light'};}}html{{font-size:{size}px!important}}"
    if is_dark():
        root += '[data-testid="stSlider"] [role="group"] > div{filter:brightness(1.6) saturate(1.1)}'
    st.markdown("<style>@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800&display=swap');"
                + root + CSS + "</style>", unsafe_allow_html=True)


CSS = """
:root{--font:'Figtree','Segoe UI',system-ui,-apple-system,Roboto,Arial,sans-serif}
html,body,.stApp,[data-testid="stApp"],[data-testid="stAppViewContainer"],[data-testid="stMain"]{
  background:linear-gradient(150deg,var(--bg1),var(--bg2))!important;background-attachment:fixed!important;
  color:var(--text)!important;font-family:var(--font)!important}
[data-testid="stHeader"]{background:transparent!important;pointer-events:none;height:0!important;min-height:0!important;overflow:hidden}
[data-testid="stToolbar"],[data-testid="stDecoration"],footer,#MainMenu{visibility:hidden;height:0}
.block-container{max-width:1180px!important;padding:1.2rem 1.5rem 2rem!important}
.stApp p,.stApp label,.stApp li,.stApp h1,.stApp h2,.stApp h3,.stApp button,.stApp input{font-family:var(--font)}
[data-testid="stMarkdownContainer"],[data-testid="stMarkdownContainer"] p{color:var(--text)}
[data-testid="stIconMaterial"]{font-family:'Material Symbols Rounded','Material Icons'!important}
[data-testid="stWidgetLabel"] p{color:var(--text)!important;font-weight:600;font-size:.9rem}
[data-testid="stCaptionContainer"] p{color:var(--muted)!important}

/* ---------- Hero panel ---------- */
.hero{position:relative;overflow:hidden;border-radius:28px;padding:2.4rem 2.2rem;min-height:640px;
  color:#fff;background:linear-gradient(155deg,#053b48 0%,#0a5f73 55%,#0e7490 100%);
  box-shadow:var(--shadow);display:flex;flex-direction:column;justify-content:space-between}
.hero *{color:#fff}
.hero .blob{position:absolute;border-radius:50%;filter:blur(40px);opacity:.45;pointer-events:none}
.hero .b1{width:260px;height:260px;background:#22d3ee;top:-70px;right:-60px;animation:float 14s ease-in-out infinite}
.hero .b2{width:220px;height:220px;background:#34d399;bottom:-80px;left:-50px;opacity:.28;animation:float 18s ease-in-out infinite reverse}
@keyframes float{0%,100%{transform:translate(0,0)}50%{transform:translate(18px,22px)}}
.hero-top,.hero-mid,.hero-bottom{position:relative;z-index:1}
.hero img{height:104px;margin-left:-14px;width:auto;display:block;margin-bottom:1.6rem}
.hero h1{font-size:2.35rem;line-height:1.12;font-weight:800;letter-spacing:-.025em;margin:0 0 .9rem;color:#fff}
.hero p.lead{font-size:1.02rem;line-height:1.55;color:#d3f1f6;max-width:30rem;margin:0}
.ecg{width:100%;height:56px;margin:1.6rem 0 .4rem;opacity:.9}
.ecg path{stroke:#67e8f9;stroke-width:2.2;fill:none;stroke-linecap:round;stroke-linejoin:round;
  stroke-dasharray:420;stroke-dashoffset:420;animation:draw 3.6s ease-in-out infinite}
@keyframes draw{0%{stroke-dashoffset:420}60%,100%{stroke-dashoffset:0}}
.feat{display:flex;gap:.8rem;align-items:flex-start;padding:.75rem .9rem;margin-bottom:.6rem;border-radius:14px;
  background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.14);backdrop-filter:blur(6px);
  transition:transform .2s ease,background .2s ease}
.feat:hover{transform:translateX(4px);background:rgba(255,255,255,.15)}
.feat .ic{flex:0 0 38px;height:38px;border-radius:11px;display:grid;place-items:center;background:rgba(103,232,249,.2);color:#a5f3fc}
.feat .ic svg{color:#a5f3fc}
.feat b{display:block;font-size:.95rem;font-weight:700}
.feat span{font-size:.84rem;color:#c2e8ee}
.tagline{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:#a5e6f0;margin-top:.9rem}

/* ---------- Form panel ---------- */
.form-head h2{font-size:1.75rem;font-weight:800;letter-spacing:-.02em;margin:1.1rem 0 .25rem;color:var(--text)}
.form-head p{color:var(--muted);margin:0 0 1.1rem;font-size:.98rem}
[data-testid="stForm"]{background:var(--card)!important;border:1px solid var(--border)!important;
  border-radius:20px!important;padding:1.4rem!important;box-shadow:var(--shadow);animation:rise .35s ease both}
.card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:1.4rem;box-shadow:var(--shadow);animation:rise .35s ease both}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}

/* segmented switch (Sign in / Create account) */
[data-testid="stButtonGroup"]{width:100%}
[data-testid="stButtonGroup"] > div{width:100%;background:var(--field);border:1px solid var(--border);border-radius:14px;padding:4px;gap:4px}
[data-testid="stButtonGroup"] button{flex:1;border:none!important;border-radius:10px!important;background:transparent!important;
  color:var(--muted)!important;font-weight:700!important;min-height:44px;transition:all .18s ease}
[data-testid="stButtonGroup"] button p{color:inherit!important;font-weight:700}
[data-testid="stButtonGroup"] button:hover{color:var(--text)!important}
[data-testid="stButtonGroup"] button[aria-checked="true"],[data-testid="stButtonGroup"] button[aria-pressed="true"],
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"]{
  background:var(--primary)!important;color:var(--on-primary)!important;box-shadow:0 4px 12px -4px var(--primary)}

/* inputs */
[data-testid="stTextInputRootElement"],[data-testid="stNumberInputContainer"]{
  background:var(--field)!important;border:1px solid var(--border)!important;border-radius:12px!important;min-height:46px;
  transition:border-color .15s,box-shadow .15s}
[data-testid="stTextInputRootElement"]:focus-within,[data-testid="stNumberInputContainer"]:focus-within{
  border-color:var(--ring)!important;box-shadow:0 0 0 3px color-mix(in srgb,var(--ring) 28%,transparent)!important}
input{background:transparent!important;color:var(--text)!important;-webkit-text-fill-color:var(--text)!important;caret-color:var(--primary)}
input::placeholder{color:var(--muted)!important;-webkit-text-fill-color:var(--muted)!important;opacity:.85}
[data-testid="stTextInputRootElement"] svg,[data-testid="stNumberInputContainer"] svg,
[data-testid="stTextInputRootElement"] [data-testid="stIconMaterial"]{color:var(--muted)!important;fill:var(--muted)!important}
[data-testid="stNumberInputContainer"] button{background:transparent!important;color:var(--muted)!important;border:none!important}
[data-testid="stNumberInputContainer"] button:hover{color:var(--primary)!important}

/* buttons */
.stButton>button,.stFormSubmitButton>button{border-radius:12px!important;min-height:46px;font-weight:700!important;
  border:1px solid var(--border)!important;background:var(--card)!important;color:var(--text)!important;transition:all .15s ease}
.stButton>button p,.stFormSubmitButton>button p{color:inherit!important;font-weight:700}
.stButton>button [data-testid="stMarkdownContainer"] p,.stFormSubmitButton>button [data-testid="stMarkdownContainer"] p,[data-testid="stButtonGroup"] button [data-testid="stMarkdownContainer"] p{color:inherit!important}
.stButton>button [data-testid="stMarkdownContainer"] p,.stFormSubmitButton>button [data-testid="stMarkdownContainer"] p{color:inherit!important}
.stButton>button:hover{border-color:var(--primary)!important;color:var(--primary)!important}
.stFormSubmitButton>button,.stButton>button[kind="primary"]{background:var(--primary)!important;border-color:var(--primary)!important;
  color:var(--on-primary)!important;box-shadow:0 8px 20px -8px var(--primary)}
.stFormSubmitButton>button:hover,.stButton>button[kind="primary"]:hover{background:var(--primary-hover)!important;border-color:var(--primary-hover)!important;
  color:var(--on-primary)!important;transform:translateY(-1px)}
.stFormSubmitButton>button:active,.stButton>button:active{transform:translateY(0) scale(.99)}
.stButton>button:focus-visible,.stFormSubmitButton>button:focus-visible{outline:3px solid var(--ring)!important;outline-offset:2px}
.st-key-theme_btn button,[data-testid="stPopover"] button{min-width:46px;padding:0 .6rem!important}
[data-testid="stPopoverBody"]{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:14px!important}
.link-row{text-align:center;color:var(--muted);margin:1rem 0 .4rem;font-size:.92rem}

/* radio cards (account type) + text size pills */
[data-testid="stRadio"] [role="radiogroup"]{gap:.6rem}
[data-testid="stRadio"] [role="radiogroup"] label{background:var(--field);border:1.5px solid var(--border);border-radius:14px;padding:.7rem .9rem;
  margin:0!important;cursor:pointer;transition:all .15s ease;flex:1}
[data-testid="stRadio"] [role="radiogroup"] label:hover{border-color:var(--primary)}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked){border-color:var(--primary);background:color-mix(in srgb,var(--primary) 12%,var(--field));
  box-shadow:0 0 0 3px color-mix(in srgb,var(--primary) 20%,transparent)}
[data-testid="stRadio"] [role="radiogroup"] label p{color:var(--text)!important;font-weight:700}
[data-testid="stRadio"] label [data-testid="stCaptionContainer"] p,[data-testid="stRadio"] label small{color:var(--muted)!important;font-weight:500}


/* button label colours (win over the generic markdown rule) */
button[data-testid^="stBaseButton"] [data-testid="stMarkdownContainer"] p{color:inherit!important}
button[kind^="primary"],button[kind^="primary"] *{color:var(--on-primary)!important}
[data-testid="stButtonGroup"] button[aria-checked="true"],[data-testid="stButtonGroup"] button[aria-checked="true"] *{color:var(--on-primary)!important}
[data-testid="stButtonGroup"] button[aria-checked="false"] *{color:var(--muted)!important}


/* theme / text-size icon buttons */
.st-key-theme_btn button,[data-testid="stPopover"] button,button[data-testid="stPopoverButton"]{
  background:var(--card)!important;color:var(--text)!important;border:1px solid var(--border)!important;
  border-radius:12px!important;min-height:44px;min-width:46px;transition:all .15s ease}
.st-key-theme_btn button *,[data-testid="stPopover"] button *,button[data-testid="stPopoverButton"] *{color:var(--text)!important;fill:var(--text)!important}
.st-key-theme_btn button:hover,[data-testid="stPopover"] button:hover{border-color:var(--primary)!important}
.st-key-theme_btn button:hover *,[data-testid="stPopover"] button:hover *{color:var(--primary)!important}
.st-key-theme_btn button:focus-visible,[data-testid="stPopover"] button:focus-visible{outline:3px solid var(--ring)!important;outline-offset:2px}


/* ---------- App shell (step 2) ---------- */
.st-key-topbar{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:.55rem .9rem;box-shadow:var(--shadow);margin-bottom:.9rem}
.st-key-topbar [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:.5rem!important;align-items:center}
.st-key-topbar [data-testid="stColumn"]{min-width:0!important}
.brandbar{display:flex;align-items:center;gap:.7rem}
.brandbar img{height:52px;width:auto;display:block}
.brandbar b{display:block;font-size:.98rem;letter-spacing:-.01em;color:var(--text)}
.brandbar span{font-size:.78rem;color:var(--muted)}
.userchip{display:flex;align-items:center;gap:.6rem;justify-content:flex-end}
.avatar{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;font-weight:800;background:var(--primary);color:var(--on-primary)}
.userchip b{display:block;font-size:.9rem;color:var(--text);line-height:1.2}
.userchip span{font-size:.74rem;color:var(--muted);text-transform:capitalize}
.pagehead{display:flex;align-items:center;gap:1.1rem;flex-wrap:wrap;border-radius:22px;padding:1.3rem 1.5rem;margin:.9rem 0 1.1rem;color:#fff;
  background:linear-gradient(155deg,#053b48,#0a5f73 60%,#0e7490);box-shadow:var(--shadow);position:relative;overflow:hidden}
.pagehead *{color:#fff}
.pagehead .ph-ic{flex:0 0 54px;height:54px;border-radius:16px;display:grid;place-items:center;background:rgba(103,232,249,.2)}
.pagehead .ph-ic svg{color:#a5f3fc}
.pagehead .ph-tx{flex:1 1 280px}
.pagehead h1{font-size:1.65rem;font-weight:800;letter-spacing:-.02em;margin:0 0 .2rem;color:#fff}
.pagehead p{margin:0;color:#cdeff5;font-size:.95rem;line-height:1.45}
.chips{display:flex;gap:.5rem;flex-wrap:wrap}
.chips span{font-size:.76rem;font-weight:600;padding:.28rem .7rem;border-radius:99px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.2);color:#e6fbff}

.st-key-form_card{background:var(--card);border:1px solid var(--border);border-radius:22px;padding:.6rem 1.4rem 1.4rem;box-shadow:var(--shadow);animation:rise .35s ease both}
.sec{display:flex;align-items:center;gap:.65rem;font-weight:800;font-size:1.02rem;color:var(--text);margin:1.2rem 0 .7rem;padding-bottom:.55rem;border-bottom:1px solid var(--border)}
.sec .si{width:32px;height:32px;border-radius:10px;display:grid;place-items:center;background:color-mix(in srgb,var(--primary) 14%,transparent);color:var(--primary)}
.sec small{margin-left:auto;font-weight:500;color:var(--muted);font-size:.8rem}
[data-testid="stSelectbox"] [data-baseweb="select"] > div,[data-testid="stSelectbox"] div:has(> input){background:var(--field)!important;border-color:var(--border)!important;border-radius:12px!important;min-height:46px}
[data-testid="stSelectbox"] *{color:var(--text)}
[data-baseweb="popover"] [role="listbox"],[data-baseweb="popover"] ul{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:12px!important}
[data-baseweb="popover"] li{background:transparent!important;color:var(--text)!important}
[data-baseweb="popover"] li:hover,[data-baseweb="popover"] li[aria-selected="true"]{background:color-mix(in srgb,var(--primary) 16%,transparent)!important}
[data-testid="stSliderThumbValue"],[data-testid="stSliderThumbValue"] p{color:var(--text)!important;font-weight:700}
[data-testid="stSliderTickBar"],[data-testid="stSliderTickBar"] p{color:var(--muted)!important}
[data-testid="stSlider"] [role="slider"]:focus-visible{outline:3px solid var(--ring)!important}
.st-key-form_card .stButton>button[kind="primary"]{min-height:52px;font-size:1.02rem;margin-top:.6rem}
.live{display:flex;align-items:baseline;justify-content:center;gap:.5rem;padding:.9rem;border-radius:16px;background:var(--field);border:1px solid var(--border);margin:.3rem 0 .4rem}
.live b{font-size:2.2rem;font-weight:800;letter-spacing:-.02em;color:var(--primary)}.live span{color:var(--muted);font-weight:600}

/* result panel */
.st-key-result_panel{position:sticky;top:1rem}
.res{border-radius:22px;padding:1.4rem;border:1.5px solid var(--border);background:var(--card);box-shadow:var(--shadow);animation:rise .45s ease both}
.res .top{display:flex;gap:.9rem;align-items:center}
.res .badge{flex:0 0 56px;height:56px;border-radius:17px;display:grid;place-items:center}
.res .pill{display:inline-block;font-size:.72rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:.2rem .6rem;border-radius:99px;margin-bottom:.3rem}
.res h3{margin:0;font-size:1.3rem;font-weight:800;line-height:1.2;color:var(--text)}
.res .advice{color:var(--muted);margin:1.1rem 0 0;line-height:1.55;font-size:.95rem}
.res .fact{margin-top:1.1rem;padding:.85rem 1rem;border-radius:14px;background:var(--field);border:1px solid var(--border)}
.res .fact .row{display:flex;justify-content:space-between;font-size:.86rem;color:var(--muted);margin-bottom:.45rem}
.res .fact .row b{color:var(--text);font-size:1rem}
.bar{height:10px;border-radius:99px;background:var(--track);overflow:hidden}
.bar i{display:block;height:100%;border-radius:99px;width:var(--w);animation:grow .9s cubic-bezier(.2,.8,.2,1) both}
@keyframes grow{from{width:0}}
.res.ok{border-color:color-mix(in srgb,var(--ok) 55%,var(--border))}.res.ok .badge,.res.ok .pill{background:var(--ok-bg);color:var(--ok)}.res.ok .bar i{background:var(--ok)}
.res.warn{border-color:color-mix(in srgb,#d97706 60%,var(--border))}.res.warn .badge,.res.warn .pill{background:var(--warn-bg);color:var(--warn)}.res.warn .bar i{background:var(--warn)}
.res.bad{border-color:color-mix(in srgb,var(--bad) 60%,var(--border))}.res.bad .badge,.res.bad .pill{background:var(--bad-bg);color:var(--bad)}.res.bad .bar i{background:var(--bad)}
.res .foot{margin-top:1.1rem;font-size:.76rem;color:var(--muted);display:flex;gap:.4rem;align-items:center}

/* explainable results + prescription */
.whyline{margin:.85rem 0 0;font-size:.92rem;line-height:1.45;color:var(--text)}
.why .whyline{margin:.35rem 0}
.why{margin-top:1.1rem;padding:.9rem 1rem;border-radius:14px;background:var(--field);border:1px solid var(--border)}
.why h4{margin:0 0 .5rem;font-size:.92rem;color:var(--text)}
.why .f{display:flex;align-items:center;gap:.7rem;padding:.5rem 0;border-top:1px solid var(--border);font-size:.82rem;color:var(--muted)}
.why .f.first{border-top:0}
.why .f .n{flex:1;line-height:1.35}.why .f .n b{display:block;color:var(--text);font-size:.88rem}
.why .f .e{font-weight:800;font-size:.8rem;white-space:nowrap;padding:.2rem .55rem;border-radius:99px}
.why .f .e.up{background:var(--bad-bg);color:var(--bad)}.why .f .e.down{background:var(--ok-bg);color:var(--ok)}
.why .note{margin:.6rem 0 0;font-size:.74rem;color:var(--muted);line-height:1.4}
.rxcard{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:1.2rem 1.3rem;box-shadow:var(--shadow);animation:rise .4s ease both}
.rxcard h3{margin:0 0 .25rem;font-size:1.15rem;color:var(--text)}
.rxcard .sum{color:var(--muted);font-size:.92rem;margin:0 0 .9rem;line-height:1.5}
.rxwarn{display:flex;gap:.7rem;align-items:flex-start;padding:.9rem 1rem;border-radius:14px;background:var(--bad-bg);color:var(--bad);font-weight:700;font-size:.9rem;line-height:1.45;margin-bottom:1rem}
.rxwarn svg{flex:0 0 auto;margin-top:.1rem}
.rxitem{display:flex;gap:.9rem;padding:.7rem 0;border-top:1px solid var(--border)}
.rxitem .k{flex:0 0 96px}
.rxitem .t{flex:1;line-height:1.45}.rxitem .t b{display:block;color:var(--text);font-size:.93rem}.rxitem .t span{color:var(--muted);font-size:.86rem}
.rx-rx{display:inline-block;margin-left:.4rem;font-size:.66rem;font-weight:800;padding:.1rem .4rem;border-radius:6px;background:var(--warn-bg);color:var(--warn);vertical-align:middle}
.empty{text-align:center;color:var(--muted);padding:2.2rem 1.2rem;border:1.5px dashed var(--border);border-radius:22px;background:color-mix(in srgb,var(--card) 60%,transparent)}
.empty .eic{width:64px;height:64px;border-radius:20px;margin:0 auto .9rem;display:grid;place-items:center;background:color-mix(in srgb,var(--primary) 12%,transparent);color:var(--primary)}
.empty b{display:block;color:var(--text);font-size:1.05rem;margin-bottom:.25rem}

[data-testid="stRadio"] [data-baseweb="radio"] > div:first-child{background:transparent!important;border:2px solid var(--muted)!important}
[data-testid="stRadio"] label:has(input:checked) [data-baseweb="radio"] > div:first-child{background:var(--primary)!important;border-color:var(--primary)!important}
[data-testid="stRadio"] [role="radiogroup"] label{padding:.6rem .85rem}
.res .pill{word-spacing:.2em}

/* ---------- Step 3: dashboard, tables, admin ---------- */
.tag{display:inline-block;font-size:.7rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;padding:.22rem .6rem;border-radius:99px;white-space:nowrap}
.tag.ok{background:var(--ok-bg);color:var(--ok)}.tag.warn{background:var(--warn-bg);color:var(--warn)}
.tag.bad{background:var(--bad-bg);color:var(--bad)}.tag.none{background:var(--field);color:var(--muted);border:1px solid var(--border)}
.banner.warn{background:var(--warn-bg)}.banner.warn *{color:var(--warn)}
.bigavatar{flex:0 0 64px;height:64px;border-radius:50%;display:grid;place-items:center;font-size:1.5rem;font-weight:800;color:#053b48;background:#a5f3fc}
.tiles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.9rem;margin:1rem 0 .8rem}
.tile{display:flex;align-items:center;gap:.9rem;padding:1rem 1.1rem;border-radius:18px;background:var(--card);border:1px solid var(--border);
  border-left:6px solid var(--border);box-shadow:var(--shadow);transition:transform .18s ease;animation:rise .4s ease both}
.tile:hover{transform:translateY(-2px)}
.tile.ok{border-left-color:var(--ok)}.tile.warn{border-left-color:#d97706}.tile.bad{border-left-color:var(--bad)}.tile.none{border-style:dashed;border-left-style:dashed;box-shadow:none;background:transparent}
.tile .tic{flex:0 0 46px;height:46px;border-radius:14px;display:grid;place-items:center;background:color-mix(in srgb,var(--primary) 12%,transparent);color:var(--primary)}
.tile.ok .tic{background:var(--ok-bg);color:var(--ok)}.tile.warn .tic{background:var(--warn-bg);color:var(--warn)}.tile.bad .tic{background:var(--bad-bg);color:var(--bad)}
.tile .tbody{flex:1;min-width:0}.tile .tt{font-weight:800;color:var(--text)}.tile .tr{color:var(--text);font-size:.9rem;overflow-wrap:anywhere}
.tile .td{color:var(--muted);font-size:.74rem;margin-top:.15rem}.tile.none .tr{color:var(--muted)}
.res.summary{margin-bottom:.2rem}.res.summary .bar{margin-top:1rem}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.9rem;margin:.4rem 0 1rem}
.kpi{padding:1rem 1.1rem;border-radius:18px;background:var(--card);border:1px solid var(--border);box-shadow:var(--shadow);animation:rise .4s ease both}
.kpi .kv{font-size:2rem;font-weight:800;letter-spacing:-.02em;color:var(--primary);line-height:1.1}.kpi .kl{color:var(--muted);font-size:.84rem;font-weight:600;margin-top:.2rem}
.actlist{padding:.4rem 1.1rem}
.act{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:.75rem 0;border-bottom:1px solid var(--border)}.act:last-child{border-bottom:none}
.act b{display:block;color:var(--text)}.act span{color:var(--muted);font-size:.85rem}.acr{text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:.2rem}.acr small{color:var(--muted);font-size:.72rem}
.req{display:flex;align-items:center;gap:.9rem;padding:.9rem 1.1rem}.req b{display:block;color:var(--text)}.req span{color:var(--muted);font-size:.85rem}
.tblwrap{overflow:auto;max-height:560px;border:1px solid var(--border);border-radius:16px;background:var(--card);box-shadow:var(--shadow);margin:.3rem 0 .4rem}
.tblwrap:focus-visible{outline:3px solid var(--ring)}
table.tbl{border-collapse:separate;border-spacing:0;width:100%;font-size:.86rem;margin:0}
table.tbl,table.tbl thead,table.tbl tbody,table.tbl tr{border:none!important;background:transparent}
table.tbl th,table.tbl td{border-left:none!important;border-right:none!important}
table.tbl th{position:sticky;top:0;z-index:1;background:var(--field);text-align:left;padding:.7rem .9rem;color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;white-space:nowrap;border-bottom:1px solid var(--border)}
table.tbl td{padding:.65rem .9rem;border-top:1px solid var(--border);white-space:nowrap;color:var(--text)}
table.tbl tbody tr:first-child td{border-top:none}table.tbl tbody tr:hover td{background:color-mix(in srgb,var(--primary) 7%,transparent)}
@media (max-width:820px){.tiles{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}

[data-testid="stButtonGroup"] button{flex:1 1 auto!important;padding:0 .5rem!important}
[data-testid="stButtonGroup"] button p,[data-testid="stButtonGroup"] button > div,[data-testid="stButtonGroup"] button span{overflow:visible!important;text-overflow:clip!important;white-space:nowrap!important;max-width:none!important}
/* buttons that carry a tooltip are wrapped differently by Streamlit, so style them by key */
.st-key-logout button{background:var(--card)!important;border:1px solid var(--border)!important;color:var(--text)!important;
  border-radius:12px!important;min-height:46px;font-weight:700!important;transition:all .15s ease}
.st-key-logout button *{color:var(--text)!important}
.st-key-logout button:hover{border-color:var(--primary)!important}.st-key-logout button:hover *{color:var(--primary)!important}
.st-key-logout button:focus-visible{outline:3px solid var(--ring)!important;outline-offset:2px}
/* helper widgets */
.hint{font-size:.82rem;margin:.25rem 0 .6rem;display:flex;align-items:center;gap:.4rem;color:var(--muted)}
.hint.ok{color:var(--ok)}.hint.bad{color:var(--bad)}
.meter{display:flex;gap:5px;margin:.35rem 0 .2rem}
.meter i{flex:1;height:6px;border-radius:99px;background:var(--track);transition:background .25s}
.meter.s1 i:nth-child(-n+1){background:#ef4444}.meter.s2 i:nth-child(-n+2){background:#f59e0b}
.meter.s3 i:nth-child(-n+3){background:#84cc16}.meter.s4 i{background:#22c55e}
.banner{display:flex;gap:.7rem;align-items:flex-start;padding:.8rem .95rem;border-radius:14px;margin:.2rem 0 1rem;font-size:.9rem;line-height:1.45}
.banner.info{background:var(--info-bg);color:var(--info)}.banner.info *{color:var(--info)}
.banner.ok{background:var(--ok-bg)}.banner.ok *{color:var(--ok)}
.banner.bad{background:var(--bad-bg)}.banner.bad *{color:var(--bad)}
.success-card{text-align:center;padding:1.2rem .5rem}
.success-card .badge{width:60px;height:60px;border-radius:50%;margin:0 auto .8rem;display:grid;place-items:center;background:var(--ok-bg);color:var(--ok)}
.success-card h3{margin:.2rem 0;color:var(--text)}.success-card p{color:var(--muted)}
.fine{color:var(--muted);font-size:.78rem;text-align:center;margin-top:.9rem}
[data-testid="stAlert"]{border-radius:14px!important}

.st-key-theme_row [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:.5rem!important}
.st-key-theme_row [data-testid="stHorizontalBlock"] > div{min-width:0!important;flex:0 0 auto!important;width:auto!important}
@media (max-width:820px){
  .st-key-logout button p{display:none}.st-key-logout button{min-width:46px;padding:0 .6rem!important}
  [data-testid="stButtonGroup"] button{padding:0 .3rem!important;font-size:.85rem}
  [data-testid="stButtonGroup"] button p{font-size:.85rem;white-space:nowrap;overflow:visible!important;text-overflow:clip!important}
  .st-key-topbar [data-testid="stColumn"]:nth-child(2){display:none}
  .brandbar span{display:none}.brandbar img{height:44px}
  .pagehead{padding:1.1rem}.pagehead h1{font-size:1.35rem}.st-key-result_panel{position:static}
  [data-testid="stButtonGroup"] > div{flex-wrap:wrap}[data-testid="stButtonGroup"] button{flex:1 1 44%}
  .st-key-form_card{padding:.4rem 1rem 1.1rem}
  .hero p.lead{display:none}.hero img{height:72px}.hero-bottom{display:none}.hero{padding:1.2rem 1.3rem}
  .hero{min-height:0;padding:1.6rem 1.3rem}.hero h1{font-size:1.7rem}.hero .feat,.hero .ecg,.hero .tagline{display:none}
  .block-container{padding:.8rem .9rem 2rem!important}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}.ecg path{stroke-dashoffset:0}}
"""
