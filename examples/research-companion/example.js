'use strict';
const slider = document.getElementById('steps');
const chart = document.getElementById('distribution');
const table = document.getElementById('probabilities');
function binomial(n, k) {
  let value = 1;
  for (let i = 1; i <= k; i++) value = value * (n - i + 1) / i;
  return value;
}
function svg(tag, attributes, text) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  if (text !== undefined) node.textContent = text;
  chart.append(node);
}
function render() {
  const n = Number(slider.value);
  document.getElementById('step-value').value = n;
  const probabilities = Array.from({ length: n + 1 }, (_, k) => binomial(n, k) / 2 ** n);
  const maximum = Math.max(...probabilities);
  const spacing = 620 / (n + 1);
  chart.replaceChildren();
  table.replaceChildren();
  chart.setAttribute('aria-label', `Exact distribution of position after ${n} independent fair steps. Expected position zero; variance ${n}.`);
  svg('line', { x1: 40, x2: 680, y1: 215, y2: 215, class: 'axis' });
  svg('line', { x1: 360, x2: 360, y1: 15, y2: 215, class: 'mean' });
  probabilities.forEach((probability, k) => {
    const position = 2 * k - n;
    const centre = 50 + spacing * (k + 0.5);
    const height = 165 * probability / maximum;
    const width = Math.min(70, spacing * 0.7);
    svg('rect', { x: centre - width / 2, y: 215 - height, width, height, class: 'bar' });
    svg('text', { x: centre, y: 240, 'text-anchor': 'middle' }, position);
    const percentage = 100 * probability;
    svg('text', { x: centre, y: 206 - height, 'text-anchor': 'middle', class: 'probability' }, `${percentage.toFixed(percentage < 0.1 ? 2 : 1)}%`);
    const row = document.createElement('tr');
    for (const text of [position, `${binomial(n, k)} / ${2 ** n}`]) {
      const cell = document.createElement('td');
      cell.textContent = text;
      row.append(cell);
    }
    table.append(row);
  });
  document.getElementById('chart-summary').textContent = `After ${n} step${n === 1 ? '' : 's'}, the expected position is still 0. The standard deviation is √${n} ≈ ${Math.sqrt(n).toFixed(2)}. ${n % 2 ? 'Zero is not even a possible final position after an odd number of steps.' : 'Zero is one possible outcome, among several.'}`;
}
slider.addEventListener('input', render);
render();
