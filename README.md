# dazzleos.org

The website for [Dazzle](https://github.com/dazzleos/dazzle): plain HTML, CSS
and JavaScript, published with GitHub Pages.

- `index.html`, `style.css`, `app.js`: the site.
- `scripts/update-store`: fetches the store's app catalogue, icons and
  screenshots into `data/` and `assets/store/` (needs curl and jq). The
  [Pages workflow](.github/workflows/pages.yml) runs it every hour, so the
  site lists the store's current apps.
- `scripts/screenshot.py`: takes `assets/screenshot.jpg` (the picture at
  the top of the page, and the one shared links show) from a computer
  running Dazzle, by its remote control: Text Editor with a note about
  dazzle camouflage, Chat in a room with a conversation (the script plays
  the other people in it), Globe, and Settings showing the board.

## Preview

```sh
scripts/update-store   # optional: refresh the apps
python3 -m http.server
```

## The screenshot

On a Raspberry Pi running Dazzle with a 1920x1080 screen, on the same
network as this computer, with Text Editor, Chat and Globe installed: turn
on the remote control (Settings, Debug) and note its code, then

```sh
scripts/screenshot.py --host <the Pi's address> --code <its code>
```

It closes the four apps' windows, opens and arranges them, types the note
and a reply in Chat, and saves the screenshot (a JPEG with Pillow, or a
PNG without). Its text, conversation and window places are at the top of
the script.
