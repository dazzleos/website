# dazzleos.org

The website for [Dazzle](https://github.com/dazzleos/dazzle): plain HTML, CSS
and JavaScript, published with GitHub Pages.

- `index.html`, `style.css`, `app.js`: the site.
- `scripts/update-store`: fetches the store's app catalogue, icons and
  screenshots into `data/` and `assets/store/` (needs curl and jq). The
  [Pages workflow](.github/workflows/pages.yml) runs it every hour, so the
  site lists the store's current apps.

## Preview

```sh
scripts/update-store   # optional: refresh the apps
python3 -m http.server
```
