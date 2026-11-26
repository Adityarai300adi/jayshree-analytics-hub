"""
ONE-STEP final UI: writes static/theme.css (theme + all animations + dashboard look) and puts the
new animated login panel into static/index.html.  Run once from the jayshree-hub folder:
    python apply_final.py
Safe to run again. Backup: static/index.html.final.bak
"""
import os, re, shutil, sys

HTML = os.path.join("static", "index.html")
CSS = os.path.join("static", "theme.css")
if not os.path.isfile(HTML):
    sys.exit("static/index.html not found. Run this from the jayshree-hub folder.")

THEME = r'''@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=Figtree:wght@400;500;600;700&display=swap');
/* Jayshree Analytics Hub - final theme (colours, login, upload, dashboard, animations) */
@property --a{syntax:'<angle>';initial-value:0deg;inherits:false}
@property --v1{syntax:'<integer>';initial-value:0;inherits:false}
@property --v2{syntax:'<integer>';initial-value:0;inherits:false}
:root{--bg:#edf2f3;--card:#fff;--tx:#10222e;--mu:#5b6f7b;--bd:#d9e3e7;--ac:#0b8576;--ac2:#f0a30a;--ac3:#2f6fe4;--ac4:#7c5cdb;--ac5:#e0524d;--hd:#0c2430;--hdt:#e8f3f4;--sh:0 1px 2px rgba(12,36,48,.06),0 14px 30px -20px rgba(12,36,48,.3);--hero:linear-gradient(115deg,#0c2430,#0f4a52 62%,#0b8576);--disp:"Bricolage Grotesque","Segoe UI",system-ui,sans-serif;--ease:cubic-bezier(.2,.7,.2,1)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#081a22;--card:#0f252f;--tx:#e7f1f3;--mu:#8fa8b2;--bd:#1b3744;--ac:#3fd3b8;--hd:#06141a;--hero:linear-gradient(115deg,#06141a,#0c3a42 65%,#0e6e63);--sh:0 1px 2px #0006,0 14px 30px -20px #000a}}
:root[data-theme="dark"]{--bg:#081a22;--card:#0f252f;--tx:#e7f1f3;--mu:#8fa8b2;--bd:#1b3744;--ac:#3fd3b8;--hd:#06141a;--hero:linear-gradient(115deg,#06141a,#0c3a42 65%,#0e6e63);--sh:0 1px 2px #0006,0 14px 30px -20px #000a}
:root[data-theme="dark"] .btn:not(.ghost):not(.light):not(.gbtn){color:#052b25}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .btn:not(.ghost):not(.light):not(.gbtn){color:#052b25}}
body{font-family:"Figtree","Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif}
h1,h2,h3,.kpi .v,.brandline{font-family:var(--disp)}
.btn{border-radius:9px;font-weight:600}
input,select{border-radius:9px;transition:border-color .15s,box-shadow .15s}
input:focus,select:focus{outline:none;border-color:var(--ac);box-shadow:0 0 0 3px color-mix(in srgb,var(--ac) 25%,transparent)}
.card{border-radius:14px}
th{text-transform:none;letter-spacing:0;font-size:12.5px}
@keyframes rise{from{opacity:0;transform:translateY(22px)}to{opacity:1;transform:none}}
@keyframes drift{to{transform:translate(90px,70px) scale(1.15)}}
@keyframes flow{to{stroke-dashoffset:-360}}
@keyframes grow{from{transform:scaleY(.3)}to{transform:scaleY(1)}}
@keyframes spin{to{--a:360deg}}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-9px)}}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
@keyframes halo{0%,100%{opacity:.35;transform:translate(-50%,-50%) scale(.9)}50%{opacity:.8;transform:translate(-50%,-50%) scale(1.12)}}
@keyframes step{0%,100%{background:color-mix(in srgb,var(--ac) 12%,var(--card));color:var(--ac)}12%,30%{background:var(--ac);color:#fff}42%{background:color-mix(in srgb,var(--ac) 12%,var(--card));color:var(--ac)}}
@keyframes draw{0%{stroke-dashoffset:220}35%,100%{stroke-dashoffset:0}}
@keyframes ring{from{stroke-dashoffset:113}to{stroke-dashoffset:4.5}}
@keyframes c1{to{--v1:12480}}@keyframes c2{to{--v2:96}}
@keyframes sweep{to{left:130%}}
/* ================= login ================= */
#login{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);place-items:stretch;padding:0;min-height:100vh}
.authwrap{width:100%;max-width:none;align-content:center;justify-items:center;padding:40px 24px;background:radial-gradient(620px 420px at 85% 8%,color-mix(in srgb,var(--ac) 11%,transparent),transparent),radial-gradient(520px 380px at 10% 100%,color-mix(in srgb,var(--ac2) 9%,transparent),transparent)}
.authwrap>*{width:min(440px,100%);animation:rise .75s var(--ease) both}
.authwrap>.brandline{animation-delay:.1s}
.authwrap>.lg{animation:rise .75s .22s var(--ease) both,spin 9s linear infinite;border:1.5px solid transparent;border-radius:18px;
 background:linear-gradient(var(--card),var(--card)) padding-box,conic-gradient(from var(--a),transparent 55%,var(--ac),var(--ac2),transparent) border-box;box-shadow:0 30px 60px -30px rgba(12,36,48,.35)}
.brandline{font-size:19px}
.lg h1{font-size:30px;letter-spacing:-.02em}
.lg .btn:not(.gbtn){position:relative;overflow:hidden}
.lg .btn:not(.gbtn)::after{content:"";position:absolute;top:0;bottom:0;left:-60%;width:40%;background:linear-gradient(100deg,transparent,#ffffff55,transparent);transform:skewX(-20deg)}
.lg .btn:not(.gbtn):hover::after{animation:sweep .7s}
.gbtn{transition:box-shadow .2s,transform .15s}.gbtn:hover{box-shadow:0 8px 20px -10px #0006}
.lg-hero{position:relative;overflow:hidden;background:linear-gradient(160deg,#061a24,#0b3a44 58%,#0b6f64);color:#eaf6f5;display:flex;align-items:center;padding:56px}
.lg-hero::before,.lg-hero::after{content:"";position:absolute;border-radius:50%;pointer-events:none;filter:blur(30px)}
.lg-hero::before{width:520px;height:520px;top:-160px;left:-140px;background:radial-gradient(circle,#35d2b05a,transparent 65%);animation:drift 15s ease-in-out infinite alternate}
.lg-hero::after{width:460px;height:460px;bottom:-140px;right:-120px;background:radial-gradient(circle,#f2a20c40,transparent 65%);animation:drift 19s ease-in-out infinite alternate-reverse}
.lg-hero .strands{position:absolute;inset:0;width:100%;height:100%}
.strand{fill:none;stroke-width:2;stroke-linecap:round;stroke-dasharray:3 15;animation:flow 6s linear infinite}
.strand.a{stroke:#35d2b0}.strand.b{stroke:#f2a20c;animation-duration:8s}.strand.c{stroke:#ffffff55;animation-duration:11s}
.lg-copy{position:relative;width:100%;max-width:480px}
.lg-copy h2{font-size:clamp(28px,3vw,42px);line-height:1.08;letter-spacing:-.025em;margin:0 0 12px;font-weight:700;animation:rise .9s .15s var(--ease) both}
.lg-copy p{font-size:16px;line-height:1.6;margin:0;color:#bfd8d8;max-width:44ch;animation:rise .9s .3s var(--ease) both}
.pv{display:grid;grid-template-columns:1.2fr 1fr;gap:14px;margin:28px 0 24px}
.pv-card{position:relative;background:#ffffff14;border:1px solid #ffffff2e;border-radius:16px;padding:14px 16px;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);box-shadow:0 18px 40px -22px #000a;animation:rise .9s var(--ease) both,float 7s ease-in-out infinite}
.pv-a{grid-row:1/3;animation-delay:.5s,1.4s}.pv-b{animation-delay:.65s,2.6s}.pv-c{animation-delay:.8s,.2s}
.pv-l{display:block;font-size:13px;color:#a9c9ca;margin-bottom:6px}
.pv-n{display:block;font-family:var(--disp);font-size:34px;font-weight:700;letter-spacing:-.02em;line-height:1.1;font-variant-numeric:tabular-nums}
.pv-u{font-size:13px;color:#a9c9ca}
.cnt1{animation:c1 2.4s 1s var(--ease) both;counter-reset:v1 var(--v1)}.cnt1::after{content:counter(v1)}
.cnt2{animation:c2 2s 1.1s var(--ease) both;counter-reset:v2 var(--v2)}.cnt2::after{content:counter(v2) "%"}
.spark{display:block;width:100%;height:46px;margin-top:10px;overflow:visible}
.spark path{fill:none;stroke:#35d2b0;stroke-width:2.5;stroke-linecap:round;stroke-dasharray:220;animation:draw 8s ease-in-out infinite}
.pv-b{display:grid;grid-template-columns:auto 1fr;column-gap:12px;align-items:center}.pv-b .pv-l{grid-column:1/3}
.ring{width:48px;height:48px;transform:rotate(-90deg)}.ring circle{fill:none;stroke-width:5}
.rg-bg{stroke:#ffffff26}.rg-fg{stroke:#f2a20c;stroke-linecap:round;stroke-dasharray:113;animation:ring 2s 1.1s var(--ease) both}
.pv-b .pv-n{font-size:26px}
.mini{display:block;width:100%;height:42px;overflow:visible}
.mini rect{fill:#35d2b0;transform-box:fill-box;transform-origin:50% 100%;animation:grow 2.2s ease-in-out infinite alternate}
.mini rect:nth-child(2){animation-delay:.25s}.mini rect:nth-child(3){animation-delay:.5s;fill:#f2a20c}.mini rect:nth-child(4){animation-delay:.75s}.mini rect:nth-child(5){animation-delay:1s}.mini rect:nth-child(6){animation-delay:1.25s;fill:#fff}
.pv-tags{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.pv-tags li{font-size:13px;padding:6px 12px;border-radius:99px;background:#ffffff14;border:1px solid #ffffff26;color:#d6eceb;animation:rise .8s var(--ease) both}
.pv-tags li:nth-child(1){animation-delay:1s}.pv-tags li:nth-child(2){animation-delay:1.12s}.pv-tags li:nth-child(3){animation-delay:1.24s}
@media (max-width:900px){#login{grid-template-columns:1fr}.lg-hero{min-height:240px;padding:30px 24px}.pv,.pv-tags,.lg-copy p{display:none}.lg-copy h2{margin:0}}
/* ================= upload ================= */
#app main>section{animation:rise .5s var(--ease) both}
.uphero h2{font-size:32px;letter-spacing:-.02em}
.drop{position:relative;overflow:hidden;border:2px solid transparent;border-radius:18px;padding:64px 20px;
 background:linear-gradient(color-mix(in srgb,var(--ac) 5%,var(--card)),var(--card)) padding-box,conic-gradient(from var(--a),var(--ac),var(--ac2),var(--ac3),var(--ac4),var(--ac)) border-box;animation:spin 7s linear infinite}
.drop:hover,.drop.over{border-color:transparent;background:linear-gradient(color-mix(in srgb,var(--ac) 12%,var(--card)),var(--card)) padding-box,conic-gradient(from var(--a),var(--ac),var(--ac2),var(--ac3),var(--ac4),var(--ac)) border-box;animation-duration:2.5s}
.drop.over{transform:scale(1.015);box-shadow:0 0 0 6px color-mix(in srgb,var(--ac) 18%,transparent)}
.drop::before{content:"";position:absolute;left:50%;top:80px;width:150px;height:150px;border-radius:50%;background:radial-gradient(circle,color-mix(in srgb,var(--ac) 38%,transparent),transparent 68%);transform:translate(-50%,-50%);animation:halo 3s ease-in-out infinite;pointer-events:none}
.drop>*{position:relative}
.drop svg{width:52px;height:52px;animation:bob 2.6s ease-in-out infinite}
.drop:hover svg{animation-duration:1.2s}
.steps span{animation:step 7.5s ease-in-out infinite}.steps span:nth-child(2){animation-delay:2.5s}.steps span:nth-child(3){animation-delay:5s}
/* ================= dashboard ================= */
header{padding:12px 24px;box-shadow:0 1px 0 #ffffff12}
.brand b{font-family:var(--disp);font-size:18px;letter-spacing:-.01em}
header nav button{border-radius:8px;opacity:.7}header nav button:hover{opacity:1}
header nav button.on{opacity:1;background:#ffffff14;box-shadow:inset 0 -2px 0 var(--ac2)}
main{padding-top:28px}
.hero{position:relative;overflow:hidden;border-radius:18px;padding:30px 32px}
.hero>*{position:relative;z-index:1}
.hero::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:.3;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 480 200'%3E%3Cg fill='none' stroke='white' stroke-width='1.6' stroke-dasharray='3 11' stroke-linecap='round'%3E%3Cpath d='M0 170C90 170 130 70 230 70S380 140 480 40'/%3E%3Cpath d='M0 140C90 140 140 40 240 40S390 110 480 10'/%3E%3Cpath d='M0 195C100 195 150 100 250 100S400 170 480 70'/%3E%3C/g%3E%3C/svg%3E") right center/auto 150% no-repeat}
.hero h2{font-size:30px;letter-spacing:-.02em}
.eyebrow{text-transform:none;letter-spacing:0;font-size:13px;font-weight:600}
.tbs{gap:8px}.tb{border-radius:10px;padding:.5em 1.05em}.tb.on{box-shadow:0 6px 14px -8px var(--ac)}
.kpi{padding:18px 20px 16px 24px;border-radius:14px}
.kpi::before{inset:0 auto 0 0;width:5px;height:auto}
.kpi .n:first-child{text-transform:none;letter-spacing:0;font-size:13px;font-weight:600}
.kpi .v{font-size:32px;font-weight:700;margin:6px 0 4px}
.sec h3{text-transform:none;letter-spacing:-.01em;font-size:18px;color:var(--tx);margin:10px 0 12px;padding-left:12px;border-left:4px solid var(--ac2)}
.card h3{font-size:16px}.ch{height:310px}.bd{border-radius:7px}
@media (max-width:640px){.hero{padding:22px}.hero h2{font-size:24px}.kpi .v{font-size:27px}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}.cnt1::after{content:"12480"}.cnt2::after{content:"96%"}.rg-fg{stroke-dashoffset:4.5}}
'''

HERO = '''<aside class="lg-hero"><svg class="strands" viewBox="0 0 600 800" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><path class="strand c" d="M-20 640C140 640 200 420 340 420S520 560 640 330"/><path class="strand a" d="M-20 560C150 560 220 330 360 330S540 470 640 240"/><path class="strand b" d="M-20 480C160 480 240 250 380 250S560 380 640 150"/><path class="strand a" d="M-20 400C170 400 260 180 400 180S570 300 640 70"/><path class="strand c" d="M-20 720C130 720 190 520 330 520S510 650 640 430"/></svg><div class="lg-copy"><h2>Every shift&#8217;s numbers, one upload away.</h2><p>Drop in today&#8217;s Excel workbook and watch production, dispatch and stock turn into a dashboard.</p><div class="pv" aria-hidden="true"><div class="pv-card pv-a"><span class="pv-l">Output today</span><b class="pv-n cnt1"></b><span class="pv-u">pieces</span><svg class="spark" viewBox="0 0 120 36"><path d="M2 30C16 28 20 14 36 17S58 31 72 19 100 5 118 8"/></svg></div><div class="pv-card pv-b"><span class="pv-l">Schedule met</span><svg class="ring" viewBox="0 0 44 44"><circle class="rg-bg" cx="22" cy="22" r="18"/><circle class="rg-fg" cx="22" cy="22" r="18"/></svg><b class="pv-n cnt2"></b></div><div class="pv-card pv-c"><span class="pv-l">Dispatch by day</span><svg class="mini" viewBox="0 0 120 40"><rect x="2" y="20" width="14" height="20" rx="3"/><rect x="22" y="12" width="14" height="28" rx="3"/><rect x="42" y="4" width="14" height="36" rx="3"/><rect x="62" y="16" width="14" height="24" rx="3"/><rect x="82" y="2" width="14" height="38" rx="3"/><rect x="102" y="10" width="14" height="30" rx="3"/></svg></div></div><ul class="pv-tags"><li>Password-protected files</li><li>Google, email code or mobile OTP</li><li>Files never stored</li></ul></div></aside>'''

s = open(HTML, encoding="utf-8", newline="").read()
if "wireEmail" not in s:
    print("NOTE: the email-OTP part (patch_index.py) is not in this index.html yet.")
if "/static/theme.css" not in s:
    if s.count("</style></head><body>") != 1:
        sys.exit("Could not add the theme link safely. Nothing was changed.")
    s = s.replace("</style></head><body>", '</style>\n<link rel="stylesheet" href="/static/theme.css">\n</head><body>')
if '<aside class="lg-hero">' in s:
    s, n = re.subn(r'<aside class="lg-hero">.*?</aside>', lambda m: HERO, s, count=1, flags=re.S)
elif s.count('<div id="login"><div class="authwrap">') == 1:
    s = s.replace('<div id="login"><div class="authwrap">', '<div id="login">' + HERO + '<div class="authwrap">')
else:
    sys.exit("Could not find the login panel. Nothing was changed.")
shutil.copyfile(HTML, HTML + ".final.bak")
open(HTML, "w", encoding="utf-8", newline="").write(s)
open(CSS, "w", encoding="utf-8", newline="").write(THEME)
print("Done. Final animated UI applied: static/theme.css written and static/index.html updated.")
