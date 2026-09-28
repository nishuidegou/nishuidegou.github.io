/* 文章留言：把「名称 + 内容」预填成 GitHub Issue，并列出该文章已有的留言。
   纯静态站点没有后端，所以提交动作在 GitHub 页面完成，列表走公开 API。 */
(function () {
  'use strict';

  var root = document.getElementById('comments');
  if (!root) { return; }

  var repo = root.getAttribute('data-repo') || '';
  var postPath = root.getAttribute('data-post') || '';
  var postTitle = root.getAttribute('data-title') || '';

  var form = root.querySelector('.comment-form');
  var nameEl = root.querySelector('#comment-name');
  var bodyEl = root.querySelector('#comment-body');
  var statusEl = root.querySelector('.comment-status');
  var listEl = root.querySelector('.comment-list');
  var itemsEl = root.querySelector('.comment-items');
  var countEl = root.querySelector('.comment-count');
  var noteEl = root.querySelector('#comment-note');

  var META_RE = /<!--\s*meta([\s\S]*?)-->/;
  var HTML_COMMENT_RE = /<!--[\s\S]*?-->/g;

  function marker() {
    return '<!-- post: ' + postPath + ' -->';
  }

  function trim(s) {
    return (s || '').replace(/^\s+|\s+$/g, '');
  }

  function now() {
    var d = new Date();
    function p(n) { return n < 10 ? '0' + n : '' + n; }
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
      ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  /* 把 Issue 正文拆成 { 留言正文, 元信息 } */
  function parse(raw) {
    var meta = {};
    var text = raw || '';
    var m = text.match(META_RE);
    var metaText = m ? m[1] : '';
    if (m) { text = text.slice(0, m.index); }
    text = text.replace(HTML_COMMENT_RE, '');
    metaText.split('\n').forEach(function (line) {
      var kv = line.match(/^\s*([^:：]+)\s*[:：]\s*(.*?)\s*$/);
      if (kv) { meta[trim(kv[1])] = trim(kv[2]); }
    });
    return { text: trim(text), meta: meta };
  }

  if (!form || !nameEl || !bodyEl) { return; }

  try {
    var saved = window.localStorage.getItem('comment-name');
    if (saved) { nameEl.value = saved; }
  } catch (e) { /* 隐私模式下忽略 */ }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();

    var name = trim(nameEl.value);
    var text = trim(bodyEl.value);
    if (!name || !text) {
      statusEl.textContent = '请填写名称和内容。';
      return;
    }

    try { window.localStorage.setItem('comment-name', name); } catch (e) { /* 忽略 */ }

    var issueBody = [
      marker(),
      '',
      text,
      '',
      '<!-- meta',
      '名称：' + name,
      '文章：' + postTitle,
      '页面：' + window.location.origin + postPath,
      '时间：' + now(),
      '-->'
    ].join('\n');

    var url = 'https://github.com/' + repo + '/issues/new' +
      '?title=' + encodeURIComponent('[留言] ' + postTitle + '｜' + name) +
      '&body=' + encodeURIComponent(issueBody);

    statusEl.textContent = '已在新标签页打开 GitHub 提交页，点「Submit new issue」完成提交。';
    window.open(url, '_blank', 'noopener');
    bodyEl.value = '';
  });

  if (!repo || !listEl || !itemsEl) { return; }

  function showNote(text) {
    if (!noteEl) { return; }
    noteEl.textContent = text;
    noteEl.hidden = false;
  }

  function render(issues) {
    var mine = issues.filter(function (it) {
      return !it.pull_request && it.body &&
        it.body.indexOf(marker()) !== -1;
    });
    if (!mine.length) {
      showNote('还没有留言，来说第一句吧。');
      return;
    }

    var frag = document.createDocumentFragment();
    mine.forEach(function (it) {
      var parsed = parse(it.body);
      var li = document.createElement('li');
      li.className = 'comment-item';

      var head = document.createElement('div');
      head.className = 'comment-item-head';

      var who = document.createElement('span');
      who.className = 'comment-item-name';
      who.textContent = parsed.meta['名称'] ||
        (it.user && it.user.login) || '匿名';
      head.appendChild(who);

      if (it.state !== 'open') {
        var tag = document.createElement('span');
        tag.className = 'comment-item-tag';
        tag.textContent = '已关闭';
        head.appendChild(tag);
      }

      var when = document.createElement('time');
      when.className = 'comment-item-time';
      when.setAttribute('datetime', it.created_at || '');
      when.textContent = parsed.meta['时间'] || (it.created_at || '').slice(0, 10);
      head.appendChild(when);
      li.appendChild(head);

      var text = document.createElement('div');
      text.className = 'comment-item-body';
      text.textContent = parsed.text;
      li.appendChild(text);

      var link = document.createElement('a');
      link.className = 'comment-item-link';
      link.href = it.html_url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = '在 GitHub 上回复 →';
      li.appendChild(link);

      frag.appendChild(li);
    });

    itemsEl.appendChild(frag);
    if (countEl) { countEl.textContent = '（' + mine.length + '）'; }
    listEl.hidden = false;
  }

  if (!window.fetch) {
    showNote('浏览器不支持加载留言列表，可直接在 GitHub 仓库查看。');
    return;
  }

  window.fetch('https://api.github.com/repos/' + repo +
    '/issues?state=all&per_page=100', {
      headers: { Accept: 'application/vnd.github+json' }
    })
    .then(function (res) {
      if (!res.ok) { throw new Error('HTTP ' + res.status); }
      return res.json();
    })
    .then(function (data) {
      if (Object.prototype.toString.call(data) === '[object Array]') { render(data); }
    })
    .catch(function () {
      showNote('留言列表暂时加载不出来（GitHub API 限流或网络问题），不影响提交。');
    });
})();
