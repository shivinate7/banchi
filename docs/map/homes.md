# Homes

A capability has one home. Read this page before you build a helper, and extend the home with a variant. A second copy needs a stated reason.

## Homes

- the table of screens — `app/src/App.tsx:ROUTES`
- every call from the browser to the server — `app/src/server.ts`
- every shape that crosses the wire — `app/src/types.ts`
- every color of the app — `app/src/tokens.css`
- what the device remembers between sittings — `app/src/deviceMemory.ts`
- reading a CSV file in the browser — `app/src/csvUpload.ts`
- cropping a card from its photograph — `identify/images.py:card_box_for`
- the batch call to the model — `identify/batch.py`
- the grammar that names which cards a run holds — `pipeline/selection.py`
- the join key of a card, for each game — `pipeline/join.py:number_index_key`
- the copies of a SKU that an import file adds — `pipeline/join.py:SkuMatch`
- the label of a card that left its box — `pipeline/join.py:departed_label`
- the price answer for the store, keyed by SKU — `pipeline/corpus.py`
- the default price threshold — `pipeline/corpus.py:DEFAULT_CUTOFF`
- re-binding a run's records to its photographs — `cli/resolve.py:realign`
- the inventory of boxes, and putting a section divider into a box — `store/master.py:Inventory`
- where the per-machine folder and port live — `server/ports.py:machine_dir`
- reading the literals of a Python file without importing it — `scripts/docs_audit/core.py:literals_from_module`
