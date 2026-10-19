window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex",
  },
  startup: {
    // Zensical's document stream handles the initial render and later visits.
    typeset: false,
    ready() {
      MathJax.startup.defaultReady();

      // Serialize renders after MathJax initializes, including cached page visits.
      document$.subscribe(() => {
        MathJax.startup.promise = MathJax.startup.promise.then(() => {
          MathJax.startup.output.clearCache();
          MathJax.typesetClear();
          MathJax.texReset();
          return MathJax.typesetPromise();
        });
      });

      component$.subscribe(({ ref }) => {
        if (ref.classList.contains("md-annotation")) {
          MathJax.startup.promise = MathJax.startup.promise.then(() =>
            MathJax.typesetPromise([ref]),
          );
        }
      });
    },
  },
};
