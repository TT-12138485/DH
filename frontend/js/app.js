/* 中文文本数字人文分析 —— 前端逻辑 */
(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const textInput = $('#text-input');
  const charCount = $('#char-count');
  const fileName = $('#file-name');
  const fileInput = $('#file-input');
  const btnAnalyze = $('#btn-analyze');
  const btnClear = $('#btn-clear');
  const analyzeStatus = $('#analyze-status');
  const results = $('#results');
  const resultHint = $('#result-hint');

  const COLOR_ACCENT = '#2f5b8f';
  const COLOR_TEAL = '#2c7a7b';
  const COLOR_GOLD = '#c9a227';
  const PALETTE = ['#2f5b8f', '#2c7a7b', '#c9a227', '#8b5e3c', '#5a7d9a',
    '#3a6b6c', '#a8763e', '#6b5b8f', '#4a8f6b', '#b0544f'];

  let currentData = null;
  const charts = {}; // 已创建的 ECharts 实例，便于 resize / 复用

  /* ---------- 输入区 ---------- */
  function updateCharCount() {
    charCount.textContent = textInput.value.length + ' 字';
  }
  textInput.addEventListener('input', updateCharCount);

  btnClear.addEventListener('click', () => {
    textInput.value = '';
    fileName.textContent = '';
    $('#custom-names').value = '';
    updateCharCount();
  });

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    fileName.textContent = '正在解析 ' + file.name + ' …';
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await fetch('/api/extract', { method: 'POST', body: fd });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || '解析失败');
      textInput.value = j.text;
      fileName.textContent = `${file.name}（${j.chars} 字）`;
      updateCharCount();
    } catch (e) {
      fileName.textContent = '';
      alert('文件解析失败：' + e.message);
    }
    fileInput.value = '';
  });

  /* ---------- Tab 切换 ---------- */
  $('#tabs').addEventListener('click', (e) => {
    const btn = e.target.closest('.tab');
    if (!btn) return;
    $$('.tab').forEach((t) => t.classList.remove('active'));
    $$('.tab-panel').forEach((p) => p.classList.remove('active'));
    btn.classList.add('active');
    $('#panel-' + btn.dataset.tab).classList.add('active');
    // 延迟 resize，确保容器可见后再渲染
    setTimeout(() => Object.values(charts).forEach((c) => c && c.resize()), 50);
  });

  /* ---------- 分析 ---------- */
  btnAnalyze.addEventListener('click', async () => {
    const text = textInput.value.trim();
    if (!text) { alert('请先输入或上传文本'); return; }
    if (text.length < 20) { alert('文本太短（少于 20 字），难以有效分析'); return; }

    const customNames = $('#custom-names').value
      .split(/[\s,，、;；]+/).map((s) => s.trim()).filter(Boolean);
    const numTopics = parseInt($('#num-topics').value, 10) || 5;

    setLoading(true);
    try {
      const r = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text, custom_names: customNames, num_topics: numTopics, top_n: 200,
        }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || '分析失败');
      currentData = j;
      renderAll(j);
      results.hidden = false;
      results.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      alert('分析失败：' + e.message);
    } finally {
      setLoading(false);
    }
  });

  function setLoading(on) {
    btnAnalyze.disabled = on;
    if (on) {
      analyzeStatus.innerHTML = '<span class="spinner"></span>正在计算，请稍候…';
    } else {
      analyzeStatus.textContent = '';
    }
  }

  /* ---------- 渲染 ---------- */
  function renderAll(d) {
    resultHint.textContent =
      `共 ${d.stats.chars} 字 · ${d.stats.words} 词 · ${d.stats.paragraphs} 段 · ${d.stats.sentences} 句`;
    renderStats(d.stats);
    renderOverviewGauge(d.sentiment.overall);
    renderFreq(d.word_freq);
    renderWordcloud(d.wordcloud);
    renderKeywords(d.keywords);
    renderLexical(d.lexical);
    renderNetwork(d.person_network);
    renderSentiment(d.sentiment);
    renderTopics(d.topics);
  }

  function chart(id) {
    if (!charts[id]) {
      const el = document.getElementById(id);
      if (!el) return null;
      charts[id] = echarts.init(el);
    }
    return charts[id];
  }

  function renderStats(s) {
    const items = [
      ['字数', s.chars], ['分词数', s.words], ['去重词', s.unique_words],
      ['段落数', s.paragraphs], ['句子数', s.sentences],
    ];
    $('#stat-grid').innerHTML = items.map(([l, n]) =>
      `<div class="stat"><div class="num">${n}</div><div class="lbl">${l}</div></div>`
    ).join('');
  }

  function renderOverviewGauge(overall) {
    const c = chart('chart-overview-gauge');
    if (!c) return;
    c.setOption({
      series: [{
        type: 'pie', radius: ['58%', '78%'],
        center: ['50%', '50%'],
        label: { show: true, formatter: '{b}\n{d}%', color: '#4b5563' },
        data: [
          { name: '积极', value: overall.positive_count, itemStyle: { color: COLOR_TEAL } },
          { name: '消极', value: overall.negative_count, itemStyle: { color: '#b0544f' } },
        ],
      }],
    });
  }

  function renderFreq(freq) {
    const c = chart('chart-freq');
    if (!c) return;
    const top = freq.slice(0, 30).reverse();
    c.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 10, right: 30, top: 10, bottom: 10, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eee' } } },
      yAxis: { type: 'category', data: top.map((x) => x.word), axisLabel: { color: '#4b5563' } },
      series: [{
        type: 'bar', data: top.map((x) => x.count),
        itemStyle: { color: COLOR_ACCENT, borderRadius: [0, 4, 4, 0] },
        barMaxWidth: 16,
      }],
    });
  }

  function renderWordcloud(wc) {
    const c = chart('chart-wordcloud');
    if (!c) return;
    const max = wc.length ? wc[0].value : 1;
    c.setOption({
      tooltip: { show: true },
      series: [{
        type: 'wordCloud',
        shape: 'circle',
        left: 'center', top: 'center', width: '92%', height: '92%',
        sizeRange: [14, 70], rotationRange: [0, 0],
        gridSize: 6, drawOutOfBound: false,
        textStyle: {
          fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif',
          fontWeight: 'normal',
          color: () => PALETTE[Math.floor(Math.random() * PALETTE.length)],
        },
        emphasis: { textStyle: { textShadowBlur: 10, textShadowColor: '#333' } },
        data: wc.slice(0, 150).map((x) => ({ name: x.name, value: x.value })),
      }],
    });
  }

  function keywordBar(id, list, color) {
    const c = chart(id);
    if (!c) return;
    const top = list.slice(0, 20).reverse();
    c.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 10, right: 30, top: 10, bottom: 10, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eee' } } },
      yAxis: { type: 'category', data: top.map((x) => x.word), axisLabel: { color: '#4b5563' } },
      series: [{
        type: 'bar', data: top.map((x) => x.score),
        itemStyle: { color: color, borderRadius: [0, 4, 4, 0] }, barMaxWidth: 16,
      }],
    });
  }

  function renderKeywords(kw) {
    keywordBar('chart-tfidf', kw.tfidf || [], COLOR_ACCENT);
    keywordBar('chart-textrank', kw.textrank || [], COLOR_TEAL);
  }

  function renderLexical(lex) {
    if (!lex) return;
    $('#lexical-stats').innerHTML = [
      ['词元总数', lex.total_tokens || 0],
      ['实词占比', Math.round((lex.content_ratio || 0) * 100) + '%'],
      ['高频搭配', (lex.bigrams || []).length],
      ['词性类别', (lex.pos || []).length],
    ].map(([l, n]) => `<div class="stat"><div class="num">${n}</div><div class="lbl">${l}</div></div>`).join('');

    // 词性分布（横向条形，tooltip 显示占比）
    const pos = chart('chart-pos');
    if (pos) {
      const items = (lex.pos || []).slice(0, 15).reverse();
      pos.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (p) => `${p[0].name}：${p[0].value} 词` },
        grid: { left: 10, right: 40, top: 10, bottom: 10, containLabel: true },
        xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eee' } } },
        yAxis: { type: 'category', data: items.map((x) => x.pos), axisLabel: { color: '#4b5563' } },
        series: [{ type: 'bar', data: items.map((x) => x.count), itemStyle: { color: COLOR_ACCENT, borderRadius: [0, 4, 4, 0] }, barMaxWidth: 18 }],
      });
    }

    // 词长分布（纵向柱状）
    const wl = chart('chart-wordlen');
    if (wl) {
      const items = lex.word_length || [];
      wl.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: 10, right: 20, top: 20, bottom: 40, containLabel: true },
        xAxis: { type: 'category', data: items.map((x) => x.length + '字'), name: '词长' },
        yAxis: { type: 'value', name: '词数', splitLine: { lineStyle: { color: '#eee' } } },
        series: [{ type: 'bar', data: items.map((x) => x.count), itemStyle: { color: COLOR_GOLD, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 44 }],
      });
    }

    // 高频搭配
    hBar('chart-bigrams', (lex.bigrams || []).slice(0, 20).map((b) => ({ label: b.word, value: b.count })), COLOR_TEAL);
  }

  function renderNetwork(net) {
    const nodes = net.nodes || [];
    const links = net.links || [];
    const cent = net.centrality || [];

    // 社区索引 → 颜色
    const communityOf = {};
    (net.communities || []).forEach((comm, ci) => comm.forEach((n) => { communityOf[n] = ci; }));

    // 统计卡片
    const topFreq = (net.top_persons && net.top_persons[0]) ? net.top_persons[0].name : '—';
    const topHub = cent.length ? cent[0].name : '—';
    const statItems = [
      ['人物数', nodes.length],
      ['关系对数', links.length],
      ['出场最多', topFreq],
      ['关系最广', topHub],
    ];
    $('#network-stats').innerHTML = statItems.map(([l, n]) =>
      `<div class="stat"><div class="num">${n}</div><div class="lbl">${l}</div></div>`
    ).join('');

    // 力导向图
    const c = chart('chart-network');
    if (c) {
      if (!nodes.length) {
        c.clear();
        c.setOption({ title: { text: '未识别到明显的人物', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } } });
      } else {
        const gNodes = nodes.map((n) => ({
          name: n.name,
          symbolSize: 10 + Math.sqrt(n.value) * 3,
          value: n.value,
          itemStyle: { color: PALETTE[(communityOf[n.name] != null ? communityOf[n.name] : 0) % PALETTE.length] },
          label: { show: true, color: '#333' },
        }));
        const gLinks = links.map((l) => ({
          source: l.source, target: l.target, value: l.value,
          lineStyle: { width: Math.min(6, l.value), opacity: 0.55, color: '#8aa3c2' },
        }));
        c.setOption({
          tooltip: { formatter: (p) => p.dataType === 'node' ? `${p.name}：出场 ${p.value} 次` : `${p.data.source} — ${p.data.target}：共现 ${p.data.value} 次` },
          series: [{
            type: 'graph', layout: 'force',
            force: { repulsion: 220, edgeLength: 90, gravity: 0.08 },
            roam: true, draggable: true,
            data: gNodes, links: gLinks,
            edgeSymbol: ['none', 'none'],
            emphasis: { focus: 'adjacency', lineStyle: { width: 4 } },
          }],
        });
      }
    }

    // 出场频次
    hBar('chart-person-freq', (net.top_persons || []).slice(0, 15).map((p) => ({ label: p.name, value: p.freq })), COLOR_ACCENT);
    // 关系强度
    hBar('chart-person-relations', (net.top_relations || []).slice(0, 15).map((r) => ({ label: `${r.a}—${r.b}`, value: r.value })), COLOR_TEAL);
    // 中心度（加权度）
    hBar('chart-person-centrality', cent.slice(0, 20).map((x) => ({ label: x.name, value: x.degree })), COLOR_GOLD);

    renderCommunities(net.communities || []);
  }

  function renderCommunities(communities) {
    const el = $('#person-communities');
    if (!communities.length) {
      el.innerHTML = '';
      return;
    }
    el.innerHTML = `<div class="card"><div class="card-title">人物社群（模块度聚类）<span class="subtitle">同一社群的人物关系更紧密</span></div>
      <div class="comm-grid">${communities.map((comm, i) =>
        `<div class="comm-block"><span class="comm-dot" style="background:${PALETTE[i % PALETTE.length]}"></span>${comm.join('、')}</div>`
      ).join('')}</div></div>`;
  }

  function renderSentiment(s) {
    const o = s.overall || {};
    const ex = s.extremes || {};

    // 统计卡片
    const score = o.score != null ? (o.score > 0 ? '+' : '') + o.score : '—';
    const posPara = ex.most_positive ? `第${ex.most_positive.index}段` : '—';
    const negPara = ex.most_negative ? `第${ex.most_negative.index}段` : '—';
    $('#sentiment-stats').innerHTML = [
      ['情感得分', score],
      ['积极占比', Math.round((o.positive_ratio || 0) * 100) + '%'],
      ['最积极段落', posPara],
      ['最消极段落', negPara],
    ].map(([l, n]) => `<div class="stat"><div class="num">${n}</div><div class="lbl">${l}</div></div>`).join('');

    // 情感倾向 gauge
    const g = chart('chart-sentiment-gauge');
    if (g) {
      const ratio = Math.round((o.positive_ratio || 0) * 100);
      g.setOption({
        series: [{
          type: 'gauge', startAngle: 210, endAngle: -30,
          min: 0, max: 100, radius: '90%',
          pointer: { show: false },
          progress: { show: true, width: 16, itemStyle: { color: COLOR_TEAL } },
          axisLine: { lineStyle: { width: 16 } },
          axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
          detail: {
            valueAnimation: true, fontSize: 30, offsetCenter: [0, '8%'],
            color: '#333', formatter: '{value}%',
          },
          title: { offsetCenter: [0, '35%'], fontSize: 13, color: '#888' },
          data: [{ value: ratio, name: o.label }],
        }],
      });
    }
    // 走势折线
    const line = chart('chart-sentiment-line');
    if (line) {
      const curve = s.curve || [];
      line.setOption({
        tooltip: { trigger: 'axis', formatter: (p) => { const d = p[0]; return `第${d.axisValue}段<br/>得分：${d.value}`; } },
        grid: { left: 40, right: 20, top: 20, bottom: 40, containLabel: true },
        xAxis: { type: 'category', data: curve.map((c) => c.index), name: '段落' },
        yAxis: { type: 'value', name: '情感得分', splitLine: { lineStyle: { color: '#eee' } } },
        series: [{
          type: 'line', data: curve.map((c) => c.score),
          smooth: true, symbol: 'circle', symbolSize: 6,
          lineStyle: { color: COLOR_ACCENT, width: 2.5 },
          itemStyle: { color: COLOR_ACCENT },
          areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(47,91,143,.25)' }, { offset: 1, color: 'rgba(47,91,143,0)' }] } },
        }],
      });
    }

    // 强度分布直方图
    const hist = chart('chart-sentiment-hist');
    if (hist) {
      const dist = s.distribution || [];
      hist.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: 10, right: 20, top: 20, bottom: 60, containLabel: true },
        xAxis: { type: 'category', data: dist.map((d) => d.range), axisLabel: { rotate: 25, color: '#8a8f98', fontSize: 10 } },
        yAxis: { type: 'value', name: '段落数', splitLine: { lineStyle: { color: '#eee' } } },
        series: [{ type: 'bar', data: dist.map((d) => d.count), itemStyle: { color: COLOR_ACCENT, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40 }],
      });
    }

    renderExtremes(ex);
    renderModifiers(s.modifiers);

    wordBar('chart-pos-words', s.positive_words || [], COLOR_TEAL);
    wordBar('chart-neg-words', s.negative_words || [], '#b0544f');
  }

  function renderExtremes(ex) {
    const el = $('#sentiment-extremes');
    const pos = ex.most_positive, neg = ex.most_negative;
    el.innerHTML = `
      <div class="extreme pos">
        <div class="extreme-head">😊 最积极段落 <span>第${pos ? pos.index : '—'}段 · 得分 ${pos ? pos.score : '—'}</span></div>
        <p>${pos ? escapeHtml(pos.text) : '—'}</p>
      </div>
      <div class="extreme neg">
        <div class="extreme-head">😟 最消极段落 <span>第${neg ? neg.index : '—'}段 · 得分 ${neg ? neg.score : '—'}</span></div>
        <p>${neg ? escapeHtml(neg.text) : '—'}</p>
      </div>`;
  }

  function renderModifiers(mod) {
    const el = $('#sentiment-modifiers');
    if (!mod) { el.innerHTML = ''; return; }
    const degree = (mod.degree_words || []).map((w) => `<span class="chip">${w.word} ×${w.count}</span>`).join('');
    const neg = (mod.negation_words || []).map((w) => `<span class="chip">${w.word} ×${w.count}</span>`).join('');
    el.innerHTML = `
      <div class="mod-row"><span class="mod-label">程度副词（${mod.degree_count} 次）</span><div class="topic-chips">${degree || '<span style="color:#999">无</span>'}</div></div>
      <div class="mod-row"><span class="mod-label">否定词（${mod.negation_count} 次）</span><div class="topic-chips">${neg || '<span style="color:#999">无</span>'}</div></div>`;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  }

  function wordBar(id, list, color) {
    const c = chart(id);
    if (!c) return;
    const top = list.slice(0, 15).reverse();
    c.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 10, right: 30, top: 10, bottom: 10, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eee' } } },
      yAxis: { type: 'category', data: top.map((x) => x.word), axisLabel: { color: '#4b5563' } },
      series: [{ type: 'bar', data: top.map((x) => x.count), itemStyle: { color, borderRadius: [0, 4, 4, 0] }, barMaxWidth: 16 }],
    });
  }

  // 通用横向条形图（[{label, value}]）
  function hBar(id, items, color) {
    const c = chart(id);
    if (!c || !items.length) return;
    const top = items.slice().reverse();
    c.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 10, right: 30, top: 10, bottom: 10, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eee' } } },
      yAxis: { type: 'category', data: top.map((x) => x.label), axisLabel: { color: '#4b5563' } },
      series: [{ type: 'bar', data: top.map((x) => x.value), itemStyle: { color, borderRadius: [0, 4, 4, 0] }, barMaxWidth: 16 }],
    });
  }

  function renderTopics(t) {
    if (t.warning || !t.topics || !t.topics.length) {
      $('#topic-stats').innerHTML = '';
      $('#topic-keywords').innerHTML = `<p style="color:#999">${t.warning || '暂无主题结果'}</p>`;
      ['chart-topics-pie', 'chart-topics-flow', 'chart-topics-heatmap'].forEach((id) => {
        const c = chart(id); if (c) c.clear();
      });
      return;
    }

    // 统计卡片
    const topTopic = t.topics.reduce((a, b) => (a.weight > b.weight ? a : b), t.topics[0]);
    const statItems = [
      ['主题数', t.num_topics],
      ['段落数', t.paragraphs],
      ['困惑度', t.perplexity != null ? t.perplexity : '—'],
      ['主导主题', `主题${topTopic.id + 1}（${(topTopic.weight * 100).toFixed(1)}%）`],
    ];
    $('#topic-stats').innerHTML = statItems.map(([l, n]) =>
      `<div class="stat"><div class="num">${n}</div><div class="lbl">${l}</div></div>`
    ).join('');

    renderTopicsPie(t.topics);
    renderTopicsFlow(t.topic_flow);
    renderTopicsHeatmap(t);
    renderTopicKeywords(t.topics);
  }

  function renderTopicsPie(topics) {
    const c = chart('chart-topics-pie');
    if (!c) return;
    c.setOption({
      tooltip: { trigger: 'item', formatter: '{b}：{d}%' },
      legend: { bottom: 0, type: 'scroll' },
      series: [{
        type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'],
        avoidLabelOverlap: true,
        label: { formatter: '{b}\n{d}%', color: '#4b5563', fontSize: 11 },
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        data: topics.map((tp, i) => ({ name: `主题${tp.id + 1}`, value: tp.weight, itemStyle: { color: PALETTE[i % PALETTE.length] } })),
      }],
    });
  }

  function renderTopicsFlow(flow) {
    const c = chart('chart-topics-flow');
    if (!c || !flow) return;
    const series = (flow.series || []).map((s, i) => ({
      name: s.name, type: 'line', stack: 'total',
      smooth: true, symbol: 'none',
      lineStyle: { width: 1, color: PALETTE[i % PALETTE.length] },
      areaStyle: { color: PALETTE[i % PALETTE.length], opacity: 0.55 },
      emphasis: { focus: 'series' },
      data: s.data,
    }));
    c.setOption({
      tooltip: { trigger: 'axis', formatter: (p) => {
        let s = p[0].axisValue + '<br/>';
        p.forEach((x) => { s += `${x.marker}${x.seriesName}：${(x.value * 100).toFixed(1)}%<br/>`; });
        return s;
      } },
      legend: { bottom: 0, type: 'scroll' },
      grid: { left: 40, right: 16, top: 24, bottom: 60, containLabel: true },
      xAxis: { type: 'category', boundaryGap: false, data: flow.labels, axisLabel: { color: '#8a8f98', interval: 'auto' } },
      yAxis: { type: 'value', max: 1, axisLabel: { formatter: (v) => (v * 100) + '%' }, splitLine: { lineStyle: { color: '#eee' } } },
      series: series,
    });
  }

  function renderTopicsHeatmap(t) {
    const h = chart('chart-topics-heatmap');
    if (!h) return;
    const docTopics = t.doc_topics || [];
    const nTopic = t.num_topics;
    const data = [];
    docTopics.forEach((d, di) => {
      d.topics.forEach((v, ti) => {
        data.push([ti, di, v]);
      });
    });
    h.setOption({
      tooltip: { position: 'top', formatter: (p) => `${p.data[2] !== undefined ? '权重 ' + (p.data[2] * 100).toFixed(1) + '%' : ''}` },
      grid: { left: 90, right: 20, top: 30, bottom: 60, containLabel: false },
      xAxis: { type: 'category', data: Array.from({ length: nTopic }, (_, i) => '主题' + (i + 1)), splitArea: { show: true } },
      yAxis: { type: 'category', data: docTopics.map((d) => d.doc), splitArea: { show: true } },
      visualMap: {
        min: 0, max: 1, calculable: true, orient: 'horizontal',
        left: 'center', bottom: 0,
        inRange: { color: ['#f4f2ee', '#b9cfe2', COLOR_ACCENT] },
      },
      series: [{
        type: 'heatmap', data: data,
        label: { show: false }, itemStyle: { borderColor: '#fff', borderWidth: 1 },
      }],
    });
  }

  function renderTopicKeywords(topics) {
    const el = $('#topic-keywords');
    el.innerHTML = topics.map((tp) => {
      const maxW = tp.keywords.length ? tp.keywords[0].weight : 1;
      const rows = tp.keywords.map((k) => {
        const pct = maxW ? (k.weight / maxW) * 100 : 0;
        return `<div class="tw-row">
          <span class="tw-label">${k.word}</span>
          <div class="tw-bar"><div class="tw-fill" style="width:${pct.toFixed(1)}%"></div></div>
          <span class="tw-val">${(k.weight * 100).toFixed(1)}%</span>
        </div>`;
      }).join('');
      return `<div class="topic-block">
        <h4>主题 ${tp.id + 1}
          <span class="topic-share">占比 ${(tp.weight * 100).toFixed(1)}%</span>
          <span class="topic-share muted">覆盖 ${tp.doc_count} 段</span>
        </h4>
        <div class="topic-words">${rows}</div>
      </div>`;
    }).join('');
  }

  /* resize */
  window.addEventListener('resize', () => Object.values(charts).forEach((c) => c && c.resize()));
})();
