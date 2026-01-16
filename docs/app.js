let RAW = [];
let activeCat = "all";

const CATS = [
  { id: "all", label: "전체" },
  { id: "rates", label: "금리" },
  { id: "inflation", label: "물가" },
  { id: "fx", label: "환율" },
  { id: "growth", label: "성장" },
  { id: "trade", label: "무역/제재" },
  { id: "financial_stability", label: "금융안정" },
  { id: "institutions", label: "국제기구/중앙은행" },
  { id: "other", label: "기타" },
];

function esc(s) {
  return (s ?? "").toString();
}

function chipEl(cat) {
  const btn = document.createElement("div");
  btn.className = "chip" + (cat.id === activeCat ? " active" : "");
  btn.textContent = cat.label;
  btn.onclick = () => {
    activeCat = cat.id;
    document.querySelectorAll(".chip").forEach(x => x.classList.remove("active"));
    btn.classList.add("active");
    render();
  };
  return btn;
}

function setChips() {
  const wrap = document.getElementById("chips");
  wrap.innerHTML = "";
  CATS.forEach(c => wrap.appendChild(chipEl(c)));
}

function matchCat(item) {
  if (activeCat === "all") return true;
  const cats = item.categories ?? [];
  return cats.includes(activeCat);
}

function matchQuery(item, q) {
  if (!q) return true;
  const t = (item.title ?? "").toLowerCase();
  const s = (item.source ?? "").toLowerCase();
  return t.includes(q) || s.includes(q);
}

function render() {
  const q = (document.getElementById("q").value ?? "").trim().toLowerCase();
  const rows = document.getElementById("rows");
  rows.innerHTML = "";

  const filtered = RAW.filter(it => matchCat(it) && matchQuery(it, q));

  document.getElementById("count").textContent = filtered.length;

  for (const it of filtered) {
    const tr = document.createElement("tr");

    const tdSource = document.createElement("td");
    tdSource.textContent = it.source ?? "-";

    const tdTitle = document.createElement("td");
    const a = document.createElement("a");
    a.href = it.link;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = it.title ?? "-";
    tdTitle.appendChild(a);

    const tdCat = document.createElement("td");
    tdCat.textContent = (it.categories ?? ["other"]).join(", ");

    const tdTime = document.createElement("td");
    tdTime.textContent = it.published_utc ?? "-";

    tr.appendChild(tdSource);
    tr.appendChild(tdTitle);
    tr.appendChild(tdCat);
    tr.appendChild(tdTime);
    rows.appendChild(tr);
  }
}

async function load() {
  // ✅ 캐시 방지(업데이트가 안 보이는 가장 흔한 원인)
  const url = `./data/latest_news.json?t=${Date.now()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);

  const data = await res.json();

  document.getElementById("updated").textContent = data.generated_at_utc ?? "-";
  document.getElementById("lookback").textContent = data.lookback_hours ?? 24;

  RAW = data.items ?? [];
  render();
}

setChips();
document.getElementById("q").addEventListener("input", () => render());

load().catch(err => {
  console.error(err);
  document.getElementById("updated").textContent = "불러오기 실패";
});

// 화면은 60초마다 갱신(데이터는 5분 단위로 갱신)
setInterval(() => load().catch(() => {}), 60_000);
