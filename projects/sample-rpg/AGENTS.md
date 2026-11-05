# Sample RPG (synthetic demo project)

Everything in this project is invented for the demo: no real game, client or product.

- Language pair: English -> Brazilian Portuguese.
- `references/` is read-only. The glossary (`references/glossary.csv`) wins over any other choice; adding a term
  asks the human.
- `jobs/<job>/source/` is the file as received: never change it.
- Work happens in `jobs/<job>/wip/`. Worker output goes to `wip/runs/` through `tools/runs.py`.
- The deliverable goes to `jobs/<job>/output/`. Overwriting a delivered file asks the human.
