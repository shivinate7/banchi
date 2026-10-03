/* THE TAB TITLE, its own module so a unit test can import it without App.tsx's CSS and React.
   ONE FIXED TITLE: "番地 " and the screen's name in lowercase ("番地 pricing", "番地 home"). The
   owner's ruling, 2026-09-23. It replaced a title that alternated on a timer between the screen and
   "番地 banchi", and a second, joined form under reduced motion. `app/index.html` carries
   "番地 banchi" for the moment before React boots.
   LOWERCASED HERE AND NOWHERE ELSE. The nav, the palette and the keyboard sheet draw the label in
   Title Case; this is the tab's own voice. `toLowerCase` rather than `toLocaleLowerCase`: the labels
   are ASCII English and the locale form has a Turkish dotted-i behaviour nobody here wants.
   THE FULFILLER'S TAB NAMES HIS TASK AND CARRIES NO BRAND (D5). */
export function tabTitle(route: { readonly label: string; readonly title?: string | null; readonly persona?: string } | undefined): string {
  const name = (route === undefined ? 'Not found' : route.title ?? route.label).toLowerCase()
  return route?.persona === 'fulfiller' ? name : `番地 ${name}`
}
