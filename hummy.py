from flask import Flask, request, jsonify, render_template_string
import sqlite3, time

app = Flask(__name__)
DB = "hummy.db"

# ---------------- DATABASE ----------------
def db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

with db() as c:
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user TEXT PRIMARY KEY,
        coins INTEGER,
        power INTEGER,
        last_seen INTEGER,
        daily INTEGER,
        refs INTEGER
    )
    """)

def get_user(uid):
    now = int(time.time())
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE user=?", (uid,)).fetchone()
        if not u:
            c.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",
                      (uid, 0, 1, now, 0, 0))
            return {"coins":0,"power":1,"last_seen":now,"daily":0}
        idle = max(0, (now - u["last_seen"]) // 10)
        coins = u["coins"] + idle
        c.execute("UPDATE users SET coins=?, last_seen=? WHERE user=?",
                  (coins, now, uid))
        return dict(u)

# ---------------- FRONTEND ----------------
PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Hummy Clicker</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<script src="https://telegram.org/js/telegram-web-app.js"></script>

<style>
body{margin:0;background:#0b1020;color:#fff;font-family:system-ui}
header{padding:15px;text-align:center;
background:linear-gradient(90deg,#00ffd5,#ff4ecd);color:#000;font-weight:800}
.container{padding:15px}
.card{background:#141b3a;border-radius:16px;padding:15px;margin-bottom:15px}
.balance{text-align:center}
.balance h1{margin:0;color:#00ffd5}
.tap{width:200px;height:200px;margin:20px auto;border-radius:50%;
background:radial-gradient(circle,#00ffd5,#0066ff);
display:flex;align-items:center;justify-content:center;
font-size:32px;font-weight:900;color:#000;
box-shadow:0 0 40px rgba(0,255,200,0.6);
transition:transform 0.1s}
.tap:active{transform:scale(0.9)}
button{width:100%;padding:12px;border:none;border-radius:12px;
background:#00ffd5;font-weight:700}
footer{position:fixed;bottom:0;left:0;right:0;display:flex;
background:#0d1330}
footer div{flex:1;text-align:center;padding:10px;font-size:13px;opacity:0.7}
footer .active{opacity:1;color:#00ffd5}
</style>
</head>

<body>
<header>🐹 Hummy Clicker</header>

<div class="container">

<div class="card balance">
<small>Coins</small>
<h1 id="coins">0</h1>
<small>Power: <span id="power">1</span></small>
</div>

<div class="tap" onclick="tap()">TAP</div>

<div class="card">
<h3>Upgrade</h3>
<p>Increase power (Cost: 10)</p>
<button onclick="upgrade()">Buy Upgrade</button>
</div>

<div class="card">
<h3>Daily Reward</h3>
<button onclick="daily()">Claim 100 Coins</button>
</div>

<div class="card">
<h3>Referral</h3>
<p id="ref"></p>
</div>

<div class="card">
<h3>Leaderboard</h3>
<ol id="board"></ol>
</div>

</div>

<footer>
<div class="active">Tap</div>
<div>Tasks</div>
<div>Wallet</div>
<div>Profile</div>
</footer>

<script>
const tg = window.Telegram.WebApp;
tg.ready();

const user = tg.initDataUnsafe?.user?.id || "guest";
document.getElementById("ref").innerText =
"Invite link: https://t.me/YOUR_BOT?start=" + user;

function refresh(){
 fetch("/state",{method:"POST",
 headers:{'Content-Type':'application/json'},
 body:JSON.stringify({user})})
 .then(r=>r.json()).then(d=>{
  coins.innerText=d.coins;
  power.innerText=d.power;
  board.innerHTML=d.lb.map(
   x=>`<li>${x.user}: ${x.coins}</li>`).join("");
 });
}

let lastTap=0;
function tap(){
 let now=Date.now();
 if(now-lastTap<200) return;
 lastTap=now;
 fetch("/tap",{method:"POST",
 headers:{'Content-Type':'application/json'},
 body:JSON.stringify({user})}).then(refresh);
}

function upgrade(){
 fetch("/upgrade",{method:"POST",
 headers:{'Content-Type':'application/json'},
 body:JSON.stringify({user})})
 .then(r=>r.json()).then(a=>{alert(a.msg);refresh();});
}

function daily(){
 fetch("/daily",{method:"POST",
 headers:{'Content-Type':'application/json'},
 body:JSON.stringify({user})})
 .then(r=>r.json()).then(a=>{alert(a.msg);refresh();});
}

refresh();
setInterval(refresh,5000);
</script>
</body>
</html>
"""

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template_string(PAGE)

@app.route("/state",methods=["POST"])
def state():
    u=get_user(request.json["user"])
    with db() as c:
        lb=c.execute("SELECT user,coins FROM users ORDER BY coins DESC LIMIT 5").fetchall()
    return jsonify(coins=u["coins"],power=u["power"],
                   lb=[dict(x) for x in lb])

@app.route("/tap",methods=["POST"])
def tap():
    uid=request.json["user"]
    with db() as c:
        c.execute("UPDATE users SET coins=coins+power WHERE user=?",(uid,))
    return jsonify(ok=True)

@app.route("/upgrade",methods=["POST"])
def upgrade():
    uid=request.json["user"]
    with db() as c:
        r=c.execute("SELECT coins FROM users WHERE user=?",(uid,)).fetchone()
        if r["coins"]>=10:
            c.execute("UPDATE users SET coins=coins-10,power=power+1 WHERE user=?",(uid,))
            return jsonify(msg="Upgrade successful 🚀")
        return jsonify(msg="Not enough coins ❌")

@app.route("/daily",methods=["POST"])
def daily():
    uid=request.json["user"]
    now=int(time.time())
    with db() as c:
        r=c.execute("SELECT daily FROM users WHERE user=?",(uid,)).fetchone()
        if now-r["daily"]>86400:
            c.execute("UPDATE users SET coins=coins+100,daily=? WHERE user=?",(now,uid))
            return jsonify(msg="Daily reward claimed 🎁")
        return jsonify(msg="Already claimed today")

# ---------------- RUN ----------------
if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)
