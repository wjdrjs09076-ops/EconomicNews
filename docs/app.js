async function loadNews() {
  // ✅ 캐시 방지(이전 주가 사이트에서 “업데이트가 안 보이는” 가장 흔한 원인)
  const url = `./data/latest_news.json?t=${Date.now()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);

  const data = await res.json();
  document.getElementById("updated").textContent = data.generated_at_utc ?? "-";

  const tbody = document.getElementById("rows");
  tbody.innerHTML = "";

  for (const it of (data.items ?? [])) {
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

    const tdTime = document.createElement("td");
    tdTime.textContent = it.published_utc ?? "-";

    tr.appendChild(tdSource);
    tr.appendChild(tdTitle);
    tr.appendChild(tdTime);
    tbody.appendChild(tr);
  }
}

loadNews().catch(err => {
  console.error(err);
  document.getElementById("updated").textContent = "불러오기 실패";
});

// 화면은 60초마다 갱신(데이터는 Actions가 5분 단위로 갱신)
setInterval(() => loadNews().catch(() => {}), 60_000);
