// X DOM 选择器集中处。X 页面改版只改这里；大面积失效时 index.js 会静默停标。
window.XRA = window.XRA || {};
window.XRA.selectors = {
  tweet: 'article[data-testid="tweet"]',
  text: '[data-testid="tweetText"]',
  statusLink: 'a[href*="/status/"]',
  userName: '[data-testid="User-Name"]',
  timelineColumn: '[data-testid="primaryColumn"]',
};
