(() => {
  'use strict';

  // Подставляем текущий год, если в подвале есть span#year.
  const year = document.getElementById('year');
  if (year) {
    year.textContent = String(new Date().getFullYear());
  }
})();
