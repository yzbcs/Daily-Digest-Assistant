/**
 * docs/assets/script.js
 * 更新日志站点的交互脚本
 */

document.addEventListener('DOMContentLoaded', function() {
  // 1. 版本卡片 hover 效果增强
  const cards = document.querySelectorAll('.version-card');
  cards.forEach(card => {
    card.addEventListener('mouseenter', () => {
      card.style.transition = 'transform 0.2s ease, border-color 0.2s ease';
    });
  });

  // 2. 复制代码功能（如果页面中有代码块）
  document.querySelectorAll('pre code').forEach(block => {
    const pre = block.parentElement;
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.textContent = '复制';
    copyBtn.style.cssText = `
      position: absolute;
      top: 8px;
      right: 8px;
      padding: 4px 10px;
      background: var(--surface-hover);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text-secondary);
      font-size: 12px;
      cursor: pointer;
      opacity: 0;
      transition: opacity 0.2s;
    `;
    
    pre.style.position = 'relative';
    pre.appendChild(copyBtn);
    
    pre.addEventListener('mouseenter', () => copyBtn.style.opacity = '1');
    pre.addEventListener('mouseleave', () => copyBtn.style.opacity = '0');
    
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(block.textContent).then(() => {
        copyBtn.textContent = '已复制';
        setTimeout(() => copyBtn.textContent = '复制', 2000);
      });
    });
  });

  // 3. 平滑滚动到锚点
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // 4. 添加当前年份到 footer
  const footerYear = document.querySelector('.site-footer p');
  if (footerYear) {
    const year = new Date().getFullYear();
    footerYear.innerHTML = footerYear.innerHTML.replace('2026', year);
  }

  // 5. 控制台彩蛋
  console.log('%c📬 Arxiv Daily Digest', 'font-size: 20px; font-weight: bold; color: #58a6ff;');
  console.log('%c更新日志站点已加载', 'font-size: 12px; color: #8b949e;');
  console.log('%cGitHub: https://github.com/yzbcs/Daily-Digest-Assistant', 'font-size: 12px; color: #3fb950;');
});
