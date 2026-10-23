const kind = document.querySelector("#kind"),
  category = document.querySelector("#category");
function categories() {
  if (!kind) return;
  [...category.options].forEach(
    (o) => (o.hidden = o.dataset.kind !== kind.value),
  );
  let x = [...category.options].find((o) => !o.hidden);
  if (x) category.value = x.value;
}
kind?.addEventListener("change", categories);
categories();
let chart;
async function trend() {
  const period = document.querySelector("#period").value;
  const data = await fetch("/api/summary?period=" + period).then((r) =>
    r.json(),
  );
  chart?.destroy();
  chart = new Chart(document.querySelector("#chart"), {
    type: "bar",
    data: {
      labels: data.map((x) => x.label),
      datasets: [
        {
          label: "Income",
          data: data.map((x) => x.income),
          backgroundColor: "#059669",
        },
        {
          label: "Expenses",
          data: data.map((x) => x.expense),
          backgroundColor: "#dc2626",
        },
      ],
    },
    options: { responsive: true, scales: { y: { beginAtZero: true } } },
  });
}
document.querySelector("#period")?.addEventListener("change", trend);
trend();
async function categoryTrend() {
  const canvas = document.querySelector('#category-chart'); if (!canvas) return;
  const data = await fetch('/api/categories').then((r) => r.json());
  new Chart(canvas, { type: 'doughnut', data: { labels: data.map(x => x.name), datasets: [{ data: data.map(x => x.total), backgroundColor: ['#d790f0','#91e7f3','#d2ff91','#eabe68','#ff858b','#9a8dff'] }] }, options: { plugins: { legend: { labels: { color: '#eee' } } } } });
}
categoryTrend();
